"""Rate-limit contract for the public search endpoint.

The public search endpoint must throttle anonymous traffic so a runaway bot
cannot exhaust embedding credits or hammer the DB. The limiter keys by
agent_id when authenticated and by remote IP otherwise, so authenticated and
anonymous traffic are accounted separately.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.core.rate_limit import limiter


@pytest.fixture()
def enable_limiter():
    """Opt the test into rate-limiter enforcement (disabled in the conftest)."""
    original = limiter.enabled
    limiter.enabled = True
    limiter.reset()
    try:
        yield
    finally:
        limiter.enabled = original
        limiter.reset()


def _make_client():
    from backend.application.service import AgentbookService
    from backend.domain.models import Agent
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


def test_anonymous_search_is_throttled_after_30_requests(enable_limiter):
    client, _ = _make_client()

    statuses = [
        client.get("/v1/search", params={"q": f"query-{i}"}).status_code
        for i in range(35)
    ]

    success_count = sum(1 for s in statuses if s == 200)
    rate_limited_count = sum(1 for s in statuses if s == 429)

    assert success_count == 30, (
        f"Expected exactly 30 successful anonymous search calls before throttling, "
        f"got {success_count}: {statuses}"
    )
    assert rate_limited_count == 5, (
        f"Expected the remaining 5 calls to be rate-limited, got {rate_limited_count}"
    )


def test_authenticated_caller_has_independent_quota(enable_limiter):
    client, api_key = _make_client()
    headers = {"Authorization": f"Bearer {api_key}"}

    # Burn the anonymous bucket first.
    for _ in range(30):
        client.get("/v1/search", params={"q": "anonymous"})
    assert client.get("/v1/search", params={"q": "anonymous"}).status_code == 429

    # An authenticated caller still gets a fresh allowance.
    response = client.get("/v1/search", params={"q": "authenticated"}, headers=headers)
    assert response.status_code == 200, response.text


def test_register_endpoint_is_throttled(enable_limiter):
    client, _ = _make_client()

    statuses = [
        client.post("/v1/auth/register", json={"model_type": "test"}).status_code
        for _ in range(12)
    ]

    success_count = sum(1 for s in statuses if s in (200, 201))
    rate_limited_count = sum(1 for s in statuses if s == 429)

    assert success_count == 10, (
        f"Expected the first 10 registration attempts to succeed, got {success_count}: {statuses}"
    )
    assert rate_limited_count == 2, (
        f"Expected the remaining 2 attempts to be rate-limited, got {rate_limited_count}"
    )
