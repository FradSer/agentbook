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


def test_given_authenticated_rest_caller_when_exceeding_300_per_minute_then_remaining_requests_are_throttled(enable_limiter):
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


@pytest.mark.parametrize(
    ("agent", "remote_addr", "attempts", "expected_successes"),
    [
        (None, "127.0.0.1", 35, 30),
        (
            Agent(
                api_key_hash="hash",
                model_type="test",
                agent_id=uuid4(),
            ),
            None,
            305,
            300,
        ),
    ],
)
def test_given_mcp_identity_tier_when_hitting_quota_then_successes_match_configured_limit(
    enable_mcp_limiters,
    agent: Agent | None,
    remote_addr: str | None,
    attempts: int,
    expected_successes: int,
):
    key = mcp_rate_key(agent, remote_addr)
    limiter_to_use = mcp_search_limiter_auth if agent else mcp_search_limiter
    successes = sum(1 for _ in range(attempts) if limiter_to_use.hit(key))
    assert successes == expected_successes
