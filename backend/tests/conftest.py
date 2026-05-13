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
