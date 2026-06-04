from __future__ import annotations

import os
from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.core.config import settings as app_settings
from backend.core.mcp_rate_limit import (
    mcp_search_limiter,
    mcp_search_limiter_auth,
    mcp_verify_limiter,
)
from backend.core.rate_limit import limiter


@contextmanager
def _disabled(lim):
    original = lim.enabled
    lim.enabled = False
    lim.reset()
    try:
        yield
    finally:
        lim.enabled = original
        lim.reset()


@pytest.fixture(autouse=True)
def isolate_runtime_settings_for_tests() -> None:
    """Run tests against in-memory repositories unless a test overrides settings.

    ``database_url`` / ``debug`` are clobbered unconditionally so every test
    still uses the in-memory repos. The Voyage and OpenRouter keys are
    clobbered only when ``RUN_REAL_EVAL`` is unset — the real-mode
    retrieval-quality eval (``backend/tests/eval/test_retrieval_quality.py``)
    opts in by exporting ``RUN_REAL_EVAL=1``, at which point we let whatever
    the operator already loaded from the root ``.env`` flow through to the
    service.
    """
    original_database_url = app_settings.database_url
    original_openrouter_api_key = app_settings.openrouter_api_key
    original_voyage_api_key = app_settings.voyage_api_key
    original_debug = app_settings.debug

    app_settings.database_url = None
    if not os.environ.get("RUN_REAL_EVAL"):
        app_settings.openrouter_api_key = None
        app_settings.voyage_api_key = None
    app_settings.debug = True

    try:
        yield
    finally:
        app_settings.database_url = original_database_url
        app_settings.openrouter_api_key = original_openrouter_api_key
        app_settings.voyage_api_key = original_voyage_api_key
        app_settings.debug = original_debug


@pytest.fixture(autouse=True)
def disable_rate_limiter_by_default():
    """Rate limiter is disabled in tests; tests that exercise it opt in via a fixture."""
    with (
        _disabled(limiter),
        _disabled(mcp_search_limiter),
        _disabled(mcp_search_limiter_auth),
        _disabled(mcp_verify_limiter),
    ):
        yield


# ---------------------------------------------------------------------------
# Shared factories — eliminate the duplicated `_make_service` / `_make_client`
# helpers that appeared in 8+ test files.
# ---------------------------------------------------------------------------


def _build_service(*, with_sandbox=None, with_evaluator=None):
    """Build an AgentbookService backed by in-memory repositories.

    Returns ``(service, author_id)`` where *author_id* is a pre-registered
    agent that can be used for write operations. Optional ``with_sandbox``
    / ``with_evaluator`` inject test doubles for the corresponding
    SandboxProvider / EvaluatorProvider — both default to ``None`` so the
    service falls back to its no-op handling.
    """
    from backend.application.service import AgentbookService
    from backend.domain.models import Agent
    from backend.infrastructure.persistence.in_memory import (
        InMemoryAgentRepository,
        InMemoryOutcomeRepository,
        InMemoryProblemRepository,
        InMemoryQueryEventRepository,
        InMemoryResearchCycleRepository,
        InMemorySolutionRepository,
    )

    agents = InMemoryAgentRepository()
    author_id = uuid4()
    agents.add(Agent(api_key_hash="test-hash", model_type="test", agent_id=author_id))

    kwargs = dict(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
        query_events=InMemoryQueryEventRepository(),
    )
    if with_sandbox is not None:
        kwargs["sandbox"] = with_sandbox
    if with_evaluator is not None:
        kwargs["evaluator"] = with_evaluator

    service = AgentbookService(**kwargs)
    return service, author_id


def _build_client():
    """Build a TestClient wired to an in-memory AgentbookService.

    Returns ``(client, api_key)`` — the api_key authenticates the pre-seeded
    agent.
    """
    from backend.application.security import generate_api_key, hash_api_key
    from backend.application.service import AgentbookService
    from backend.domain.models import Agent
    from backend.infrastructure.persistence.in_memory import (
        InMemoryAgentRepository,
        InMemoryOutcomeRepository,
        InMemoryProblemRepository,
        InMemoryResearchCycleRepository,
        InMemorySolutionRepository,
    )
    from backend.main import create_app
    from backend.presentation.api.deps import get_service

    agents = InMemoryAgentRepository()
    api_key = generate_api_key()
    agents.add(
        Agent(
            api_key_hash=hash_api_key(api_key),
            model_type="test",
            agent_id=uuid4(),
        )
    )

    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )

    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False), api_key


@pytest.fixture()
def service_and_author():
    """Fixture that provides ``(service, author_id)``."""
    return _build_service()


@pytest.fixture()
def client_and_key():
    """Fixture that provides ``(TestClient, api_key)``."""
    return _build_client()


# ---------------------------------------------------------------------------
# Rate-limiter opt-in fixtures (previously duplicated in 3 files).
# ---------------------------------------------------------------------------


@pytest.fixture()
def enable_limiter():
    """Opt the test into REST rate-limiter enforcement."""
    original = limiter.enabled
    limiter.enabled = True
    limiter.reset()
    try:
        yield
    finally:
        limiter.enabled = original
        limiter.reset()


@pytest.fixture()
def enable_mcp_limiters():
    """Opt the test into MCP rate-limiter enforcement (both tiers)."""
    originals = (mcp_search_limiter.enabled, mcp_search_limiter_auth.enabled)
    mcp_search_limiter.enabled = True
    mcp_search_limiter_auth.enabled = True
    mcp_search_limiter.reset()
    mcp_search_limiter_auth.reset()
    try:
        yield
    finally:
        mcp_search_limiter.enabled, mcp_search_limiter_auth.enabled = originals
        mcp_search_limiter.reset()
        mcp_search_limiter_auth.reset()


@pytest.fixture()
def enable_mcp_limiter():
    """Opt the test into anonymous-only MCP rate-limiter enforcement."""
    original = mcp_search_limiter.enabled
    mcp_search_limiter.enabled = True
    mcp_search_limiter.reset()
    try:
        yield
    finally:
        mcp_search_limiter.enabled = original
        mcp_search_limiter.reset()


@pytest.fixture()
def enable_mcp_verify_limiter():
    """Opt the test into MCP verify-tool per-agent rate-limit enforcement."""
    original = mcp_verify_limiter.enabled
    mcp_verify_limiter.enabled = True
    mcp_verify_limiter.reset()
    try:
        yield
    finally:
        mcp_verify_limiter.enabled = original
        mcp_verify_limiter.reset()


# ---------------------------------------------------------------------------
# Cross-transport contract harness (shared by feature + unit parity tests).
#
# Both transport callers are bound to ONE in-memory ``AgentbookService`` so a
# parity test compares two serializations of the same logical read. Heavy
# imports stay lazy (matching ``_build_service`` above) to keep conftest import
# cheap and avoid import-order coupling.
# ---------------------------------------------------------------------------


class _FaultEmbeddingProvider:
    """Deterministic ``EmbeddingProvider`` double for fault injection.

    Modes:

    * ``"slow"`` — blocks for ``delay_seconds`` before returning a fixed vector,
      so latency budgets can be asserted without a real network round-trip.
    * ``"failing"`` — raises, exercising the service's swallow-and-fallback path.
    * ``"dimension_mismatch"`` — returns a vector of the wrong length, exercising
      the misconfig guard (Voyage 1024-dim vs legacy ``vector(1536)``).
    """

    def __init__(self, mode: str, *, delay_seconds: float = 0.5) -> None:
        self._mode = mode
        self._delay_seconds = delay_seconds

    def embed(self, text: str, *, input_type: str = "query") -> list[float]:
        if self._mode == "slow":
            import time

            time.sleep(self._delay_seconds)
            return [0.0] * 1024
        if self._mode == "failing":
            raise RuntimeError("embedding provider unavailable")
        if self._mode == "dimension_mismatch":
            return [0.0] * 1536
        raise ValueError(f"unknown embedding fault mode: {self._mode}")


def _build_contract_service(*, embedding_provider=None):
    """``(service, ctx)`` backed by in-memory repos for transport-parity tests."""
    from backend.application.service import AgentbookService
    from backend.domain.models import Agent
    from backend.infrastructure.persistence.in_memory import (
        InMemoryAgentRepository,
        InMemoryOutcomeRepository,
        InMemoryProblemRepository,
        InMemoryResearchCycleRepository,
        InMemorySolutionRepository,
    )

    agents = InMemoryAgentRepository()
    problems = InMemoryProblemRepository()
    solutions = InMemorySolutionRepository()
    outcomes = InMemoryOutcomeRepository()
    author = Agent(api_key_hash="h", model_type="claude-sonnet-4-5", agent_id=uuid4())
    agents.add(author)
    service = AgentbookService(
        agents=agents,
        problems=problems,
        solutions=solutions,
        outcomes=outcomes,
        research_cycles=InMemoryResearchCycleRepository(),
        embedding_provider=embedding_provider,
    )
    ctx = {
        "agents": agents,
        "problems": problems,
        "solutions": solutions,
        "outcomes": outcomes,
        "author": author,
    }
    return service, ctx


@pytest.fixture()
def contract_service():
    """``(service, ctx)`` backed by in-memory repos, no embedding provider."""
    return _build_contract_service()


@pytest.fixture()
def rest_client(contract_service):
    """REST ``/v1/search`` caller bound to the shared ``contract_service``."""
    from backend.tests.unit._helpers.transports import rest_search

    service, _ = contract_service

    def _call(query, **kwargs):
        return rest_search(service, query, **kwargs)

    return _call


@pytest.fixture()
def mcp_client(contract_service):
    """MCP ``recall`` caller bound to the shared ``contract_service``."""
    from backend.tests.unit._helpers.transports import mcp_recall

    service, _ = contract_service

    def _call(query, **kwargs):
        return mcp_recall(service, query, **kwargs)

    return _call


@pytest.fixture()
def assert_transport_parity(rest_client, mcp_client):
    """Assert REST and MCP ``best_solution`` agree on *fields* for one query.

    Returns the REST ``best_solution`` dict so a caller can make additional
    assertions on the agreed payload.
    """
    from backend.tests.unit._helpers.transports import best_solution_for

    def _assert(query, fields):
        rest_best = best_solution_for(rest_client(query))
        mcp_best = best_solution_for(mcp_client(query))
        assert rest_best is not None, "REST search returned no best_solution"
        assert mcp_best is not None, "MCP recall returned no best_solution"
        for field in fields:
            assert field in rest_best, f"REST best_solution missing key {field!r}"
            assert field in mcp_best, f"MCP best_solution missing key {field!r}"
            assert rest_best[field] == mcp_best[field], (
                f"transport divergence on {field!r}: "
                f"REST={rest_best[field]!r} MCP={mcp_best[field]!r}"
            )
        return rest_best

    return _assert


@pytest.fixture()
def embedding_fault():
    """Factory for a deterministic faulty embedding provider.

    ``embedding_fault("slow" | "failing" | "dimension_mismatch")`` returns a
    provider double to pass into ``AgentbookService(embedding_provider=...)``.
    """

    def _factory(mode, *, delay_seconds=0.5):
        return _FaultEmbeddingProvider(mode, delay_seconds=delay_seconds)

    return _factory
