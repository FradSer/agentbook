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


def _status_counts(statuses: list[int], *, success_codes: tuple[int, ...]) -> tuple[int, int]:
    success_count = sum(1 for status in statuses if status in success_codes)
    rate_limited_count = sum(1 for status in statuses if status == 429)
    return success_count, rate_limited_count


def _run_requests(client: TestClient, *, method: str, count: int) -> list[int]:
    if method == "search":
        return [
            client.get("/v1/search", params={"q": f"query-{i}"}).status_code
            for i in range(count)
        ]
    return [
        client.post("/v1/auth/register", json={"model_type": "test"}).status_code
        for _ in range(count)
    ]


@pytest.mark.parametrize(
    ("method", "attempts", "expected_success", "expected_rate_limited", "success_codes"),
    [
        ("search", 35, 30, 5, (200,)),
        ("register", 12, 10, 2, (200, 201)),
    ],
)
def test_given_anonymous_caller_when_exceeding_limit_then_excess_requests_are_throttled(
    enable_limiter,
    method: str,
    attempts: int,
    expected_success: int,
    expected_rate_limited: int,
    success_codes: tuple[int, ...],
):
    client, _ = _make_client()

    statuses = _run_requests(client, method=method, count=attempts)
    success_count, rate_limited_count = _status_counts(
        statuses, success_codes=success_codes
    )

    assert success_count == expected_success, (
        f"{method} expected {expected_success} successful calls, got {success_count}: {statuses}"
    )
    assert rate_limited_count == expected_rate_limited, (
        f"{method} expected {expected_rate_limited} throttled calls, got {rate_limited_count}"
    )


def test_given_anonymous_bucket_is_exhausted_when_request_is_authenticated_then_it_has_independent_quota(enable_limiter):
    client, api_key = _make_client()
    headers = {"Authorization": f"Bearer {api_key}"}

    # Burn the anonymous bucket first.
    for _ in range(30):
        client.get("/v1/search", params={"q": "anonymous"})
    assert client.get("/v1/search", params={"q": "anonymous"}).status_code == 429

    # An authenticated caller still gets a fresh allowance.
    response = client.get("/v1/search", params={"q": "authenticated"}, headers=headers)
    assert response.status_code == 200, response.text
