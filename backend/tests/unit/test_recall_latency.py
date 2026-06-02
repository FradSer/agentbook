"""Contract tests: bounded recall latency on the read contract.

Feature file: backend/tests/features/recall-latency.feature

Recall is an agent's near-free FIRST move on hitting an error. A recall on a
novel query must return within a bounded time even when the embedding provider
is slow or misconfigured: ``VoyageEmbeddingProvider`` constructs a bounded
client (tight timeout, no SDK-internal retry) and the live ``embed`` path
carries an empty retry budget so it never performs the synchronous 1s + 2s + 4s
blocking sleep storm on the request path. Full retry is retained only on the
offline ``embed_documents`` backfill path.

All embedding I/O is faked — no real Voyage network call (CODE-TEST-01). The
retry-storm double models the *old* blocking behaviour so the Red assertions
have a real failure mode to catch.
"""

from __future__ import annotations

import time
from contextlib import contextmanager

import backend.infrastructure.embeddings.voyage as voyage_mod
from backend.tests.conftest import _build_contract_service, _build_service

# Budgets are generous relative to the contract (sub-second target) so the
# suite stays stable on a loaded CI box while still catching a multi-second
# retry storm (the old path slept 1 + 2 + 4 = 7s).
_RECALL_BUDGET_SECONDS = 2.0
_WRITE_BUDGET_SECONDS = 2.0


class _FakeEmbeddingsResponse:
    def __init__(self, vectors):
        self.embeddings = vectors


class _StormClient:
    """Stand-in for ``voyageai.Client`` that records construction kwargs and
    sleeps before raising, mimicking an unresponsive provider whose every call
    fails after the configured client timeout."""

    last_init_kwargs: dict | None = None

    def __init__(self, **kwargs):
        type(self).last_init_kwargs = kwargs
        self.embed_calls = 0
        # Per-call cost the *old* code paid via time.sleep between retries.
        self._per_call_sleep = 0.05

    def embed(self, *args, **kwargs):
        self.embed_calls += 1
        time.sleep(self._per_call_sleep)
        raise RuntimeError("voyage provider unresponsive")


class _StubVoyageModule:
    Client = _StormClient


@contextmanager
def _patched_voyage():
    """Swap the module-level ``voyageai`` reference for a stub Client."""
    original = voyage_mod.voyageai
    voyage_mod.voyageai = _StubVoyageModule
    _StormClient.last_init_kwargs = None
    try:
        yield
    finally:
        voyage_mod.voyageai = original


# --- Scenario: Slow provider degrades fast, not after a retry storm ---------
# (asserted at the VoyageEmbeddingProvider level — that is where the storm lives)


def test_live_query_embed_has_no_blocking_retry_budget():
    """The live ``embed`` path must carry an empty retry-delay budget so it
    never sleeps 1s + 2s + 4s on the request path."""
    delays = getattr(voyage_mod, "_LIVE_RETRY_DELAYS_SECONDS", None)
    assert delays == (), (
        "live query path must define an empty _LIVE_RETRY_DELAYS_SECONDS "
        f"(got {delays!r})"
    )


def test_live_query_embed_aborts_fast_without_retry_storm():
    """A live query against an unresponsive provider returns (raising) within a
    tight bound — it does NOT block on synchronous 1s + 2s + 4s retry sleeps."""
    with _patched_voyage():
        provider = voyage_mod.VoyageEmbeddingProvider(api_key="x")
        start = time.perf_counter()
        raised = False
        try:
            provider.embed("a novel query", input_type="query")
        except Exception:
            raised = True
        elapsed = time.perf_counter() - start

    assert raised, "an unresponsive provider must surface the failure"
    # Old path slept 7s across three retries; capped live path makes one attempt.
    assert elapsed < 1.0, f"live embed blocked for {elapsed:.2f}s (retry storm)"


def test_voyage_client_constructed_with_bounded_timeout():
    """The Voyage client is built with a tight timeout and no SDK-internal retry
    so a hung connection aborts at the client timeout, not after a storm."""
    with _patched_voyage():
        voyage_mod.VoyageEmbeddingProvider(api_key="x")
        init_kwargs = _StormClient.last_init_kwargs or {}

    assert init_kwargs.get("timeout") is not None, "client needs a bounded timeout"
    assert init_kwargs["timeout"] <= 5.0, "client timeout must be tight (<= 5s)"
    assert init_kwargs.get("max_retries", None) == 0, (
        "SDK-internal retries must be disabled on the live path"
    )


def test_document_backfill_path_keeps_full_retry():
    """The offline ``embed_documents`` backfill path retains the full retry
    budget — only the live request path is capped."""
    retry = getattr(voyage_mod, "_RETRY_DELAYS_SECONDS", None)
    assert retry == (1.0, 2.0, 4.0), (
        f"backfill retry budget must be retained (got {retry!r})"
    )


# --- Scenario: Slow embedding provider degrades fast (service level) --------


def test_recall_degrades_to_keyword_fallback_within_budget():
    """With an unresponsive Voyage provider, ``search_problems`` swallows the
    embed failure and serves the keyword path within the latency budget — it
    does not pay the live-path retry storm. Uses the real provider (patched
    stub client) so the assertion reflects the actual capped live path."""
    with _patched_voyage():
        provider = voyage_mod.VoyageEmbeddingProvider(api_key="x")
        service, ctx = _build_contract_service(embedding_provider=provider)
        service.create_problem(
            author_id=ctx["author"].agent_id,
            description="postgres connection pool exhausted under load",
        )

        start = time.perf_counter()
        payload = service.search_problems(
            query="postgres connection pool exhausted under load", limit=5
        )
        elapsed = time.perf_counter() - start

    # The service must not pay the 7s-per-call retry storm on the request path.
    assert elapsed < _RECALL_BUDGET_SECONDS, f"recall took {elapsed:.2f}s"
    assert payload["results"], "keyword fallback should still recover the row"


# --- Scenario: A miss is cheap ----------------------------------------------


def test_recall_miss_is_cheap_and_honest():
    """A query matching nothing returns fast and reports the miss honestly."""
    service, ctx = _build_contract_service()
    service.create_problem(
        author_id=ctx["author"].agent_id,
        description="totally unrelated note about kubernetes ingress",
    )

    start = time.perf_counter()
    payload = service.search_problems(
        query="a query that matches absolutely nothing zzzqqq", limit=5
    )
    elapsed = time.perf_counter() - start

    assert elapsed < _RECALL_BUDGET_SECONDS
    assert payload["no_good_match"] is True
    assert payload["search_mode"] == "no_match"


# --- Scenario: Embed-on-write does not dominate contribute latency ----------


def test_contribute_does_not_block_on_retry_storm_embed():
    """A slow/unresponsive document embed on the write path must not block the
    POST /v1/problems response for multiple seconds via a retry storm."""
    service, author_id = _build_service()
    with _patched_voyage():
        provider = voyage_mod.VoyageEmbeddingProvider(api_key="x")
        service._embedding_provider = provider

        start = time.perf_counter()
        problem = service.create_problem(
            author_id=author_id,
            description="A brand new problem about flaky CI on macos runners",
        )
        elapsed = time.perf_counter() - start

    assert problem is not None, "the write must succeed even when embed fails"
    assert elapsed < _WRITE_BUDGET_SECONDS, (
        f"contribute blocked for {elapsed:.2f}s on a synchronous embed storm"
    )
