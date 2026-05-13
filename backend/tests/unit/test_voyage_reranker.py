"""Unit tests for the Voyage cross-encoder reranker.

Mocks ``voyageai`` so the suite is hermetic. Covers:

* Happy path: rerank result preserves index ordering returned by the API
* Token-bucket exhaustion → identity-order fallback (NoOp), counter ticks
* Upstream exception → identity-order fallback, counter ticks
* Empty candidate list short-circuits without an API call
* ``resolve_rerank_fn`` returns ``noop_rerank`` when key/SDK missing
* The dedicated ``noop_rerank`` is a true identity slice up to ``top_k``
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.core.config import settings
from backend.infrastructure.reranking import noop_rerank
from backend.infrastructure.reranking import voyage as voyage_mod


def _fake_voyageai_with_results(results):
    fake = MagicMock()
    client = MagicMock()
    client.rerank.return_value = SimpleNamespace(results=results)
    fake.Client.return_value = client
    return fake, client


def test_rerank_orders_indices_per_voyage_response(monkeypatch):
    fake, client = _fake_voyageai_with_results(
        [
            SimpleNamespace(index=2, relevance_score=0.91),
            SimpleNamespace(index=0, relevance_score=0.55),
            SimpleNamespace(index=1, relevance_score=0.42),
        ]
    )
    monkeypatch.setattr(voyage_mod, "voyageai", fake)
    rer = voyage_mod.VoyageReranker(api_key="ak_test", model="rerank-2.5-lite")

    order = rer("query", ["a", "b", "c"], top_k=3)

    assert order == [2, 0, 1]
    client.rerank.assert_called_once_with(
        query="query",
        documents=["a", "b", "c"],
        model="rerank-2.5-lite",
        top_k=3,
    )


def test_empty_candidates_short_circuits_without_api_call(monkeypatch):
    fake, client = _fake_voyageai_with_results([])
    monkeypatch.setattr(voyage_mod, "voyageai", fake)
    rer = voyage_mod.VoyageReranker(api_key="ak_test")
    assert rer("q", [], top_k=10) == []
    client.rerank.assert_not_called()


def test_token_bucket_refusal_falls_back_to_noop(monkeypatch):
    fake, client = _fake_voyageai_with_results(
        [SimpleNamespace(index=0, relevance_score=0.99)]
    )
    monkeypatch.setattr(voyage_mod, "voyageai", fake)
    # Tiny bucket — first call passes, second is refused.
    rer = voyage_mod.VoyageReranker(api_key="ak_test", rate_limit_rpm=1)
    rer("q", ["a"], top_k=1)
    second = rer("q", ["a", "b"], top_k=2)
    # Refused call returns identity order; counter ticks once.
    assert second == [0, 1]
    assert rer.skipped_calls == 1


def test_upstream_error_falls_back_to_noop(monkeypatch):
    fake = MagicMock()
    client = MagicMock()
    client.rerank.side_effect = RuntimeError("simulated 500")
    fake.Client.return_value = client
    monkeypatch.setattr(voyage_mod, "voyageai", fake)
    rer = voyage_mod.VoyageReranker(api_key="ak_test")
    order = rer("q", ["a", "b", "c"], top_k=3)
    assert order == [0, 1, 2]
    assert rer.skipped_calls == 1


def test_resolver_returns_noop_when_key_missing(monkeypatch):
    monkeypatch.setattr(voyage_mod, "voyageai", MagicMock())
    monkeypatch.setattr(settings, "voyage_api_key", None)
    assert voyage_mod.resolve_rerank_fn() is noop_rerank


def test_resolver_returns_noop_when_voyageai_missing(monkeypatch):
    monkeypatch.setattr(voyage_mod, "voyageai", None)
    monkeypatch.setattr(settings, "voyage_api_key", "ak_test")
    assert voyage_mod.resolve_rerank_fn() is noop_rerank


def test_resolver_returns_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(voyage_mod, "voyageai", MagicMock())
    monkeypatch.setattr(settings, "voyage_api_key", "ak_test")
    monkeypatch.setattr(settings, "rerank_enabled", False)
    assert voyage_mod.resolve_rerank_fn() is noop_rerank


def test_resolver_builds_voyage_when_all_present(monkeypatch):
    fake = MagicMock()
    fake.Client.return_value = MagicMock()
    monkeypatch.setattr(voyage_mod, "voyageai", fake)
    monkeypatch.setattr(settings, "voyage_api_key", "ak_test")
    monkeypatch.setattr(settings, "rerank_enabled", True)
    monkeypatch.setattr(settings, "voyage_rerank_model", "rerank-2.5-lite")
    fn = voyage_mod.resolve_rerank_fn()
    assert isinstance(fn, voyage_mod.VoyageReranker)


def test_noop_rerank_returns_identity_truncated_to_top_k():
    assert noop_rerank("q", ["a", "b", "c", "d"], top_k=2) == [0, 1]
    assert noop_rerank("q", ["a", "b", "c"], top_k=10) == [0, 1, 2]
    assert noop_rerank("q", [], top_k=5) == []


def test_rate_limit_bucket_window_expiry():
    bucket = voyage_mod._RateLimitBucket(capacity=2, window_seconds=0.05)
    assert bucket.acquire() is True
    assert bucket.acquire() is True
    assert bucket.acquire() is False
    time.sleep(0.06)
    # After the window slides past, the bucket refills.
    assert bucket.acquire() is True
