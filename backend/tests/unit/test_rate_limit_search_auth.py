"""Authenticated callers get a higher quota (300/min) than anonymous (30/min)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.core.mcp_rate_limit import (
    mcp_rate_key,
    mcp_search_limiter,
    mcp_search_limiter_auth,
)
from backend.core.rate_limit import limiter
from backend.domain.models import Agent


@pytest.fixture()
def enable_limiter():
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


def _make_client():
    from backend.application.service import AgentbookService
    from backend.infrastructure.persistence.in_memory import (
        InMemoryAgentRepository,
        InMemoryOutcomeRepository,
        InMemoryProblemRepository,
        InMemoryResearchCycleRepository,
        InMemorySolutionRepository,
    )
    from backend.infrastructure.security import generate_api_key, hash_api_key
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


def test_authenticated_caller_throttled_above_300_per_minute(enable_limiter):
    client, api_key = _make_client()
    headers = {"Authorization": f"Bearer {api_key}"}

    statuses = [
        client.get("/v1/search", params={"q": f"q-{i}"}, headers=headers).status_code
        for i in range(305)
    ]

    success_count = sum(1 for s in statuses if s == 200)
    rate_limited_count = sum(1 for s in statuses if s == 429)

    assert success_count == 300, (
        f"Authenticated quota should be exactly 300/min, got {success_count} successes"
    )
    assert rate_limited_count == 5, (
        f"Expected the remaining 5 calls to be rate-limited, got {rate_limited_count}"
    )


def test_mcp_anonymous_throttled_at_30(enable_mcp_limiters):
    """MCP anonymous caller hits the 30/min ceiling."""
    key = mcp_rate_key(None, "127.0.0.1")
    successes = sum(1 for _ in range(35) if mcp_search_limiter.hit(key))
    assert successes == 30


def test_mcp_authenticated_throttled_at_300(enable_mcp_limiters):
    """MCP authenticated caller has the 300/min ceiling."""
    agent = Agent(
        api_key_hash="hash",
        model_type="test",
        agent_id=uuid4(),
    )
    key = mcp_rate_key(agent, None)
    successes = sum(1 for _ in range(305) if mcp_search_limiter_auth.hit(key))
    assert successes == 300
