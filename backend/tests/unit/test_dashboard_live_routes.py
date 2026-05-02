"""REST contract for GET /v1/dashboard/research/live.

Public-read snapshot endpoint that the live-research banner polls when SSE is
unavailable. Reads share the dynamic_search_limit (30/min anonymous, 300/min
authenticated). Cache-Control is "no-store" because the data is real-time.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from backend.application.service import AgentbookService
from backend.core.config import settings as app_settings
from backend.domain.models import Agent, Problem
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)
from backend.presentation.api.schemas import LiveResearchSnapshotResponse
from backend.tests.conftest import _build_client


def _seed_active_problem(service: AgentbookService, author_id) -> Problem:
    started_at = datetime.now(tz=UTC) - timedelta(seconds=30)
    problem = Problem(
        author_id=author_id,
        description="Active research problem with sufficient description length.",
        review_status="approved",
        research_started_at=started_at,
        solution_count=2,
        best_confidence=0.7,
    )
    service._problems.add(problem)
    return problem


def _build_client_with_active_problem():
    """Mirror conftest._build_client but pre-seed an actively researched problem."""
    from backend.application.security import generate_api_key, hash_api_key
    from backend.main import create_app
    from backend.presentation.api.deps import get_service

    agents = InMemoryAgentRepository()
    api_key = generate_api_key()
    author_id = uuid4()
    agents.add(
        Agent(
            api_key_hash=hash_api_key(api_key),
            model_type="test",
            agent_id=author_id,
        )
    )
    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    _seed_active_problem(service, author_id)

    from fastapi.testclient import TestClient

    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False), api_key


def test_given_anonymous_caller_when_getting_live_snapshot_then_returns_200():
    client, _ = _build_client()

    response = client.get("/v1/dashboard/research/live")

    assert response.status_code == 200, response.text


def test_given_response_when_validating_against_schema_then_payload_matches():
    client, _ = _build_client()

    response = client.get("/v1/dashboard/research/live")

    assert response.status_code == 200, response.text
    LiveResearchSnapshotResponse.model_validate(response.json())


def test_given_one_fresh_research_problem_when_getting_snapshot_then_active_has_one_item():
    client, _ = _build_client_with_active_problem()

    response = client.get("/v1/dashboard/research/live")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload["active"]) == 1
    item = payload["active"][0]
    assert item["solution_count"] == 2
    assert item["best_confidence"] == 0.7
    assert item["elapsed_seconds"] >= 0


def test_given_no_active_research_when_getting_snapshot_then_active_is_empty():
    client, _ = _build_client()

    response = client.get("/v1/dashboard/research/live")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["active"] == []
    assert payload["last_cycle_at"] is None


def test_given_response_when_inspecting_headers_then_cache_control_is_no_store():
    client, _ = _build_client()

    response = client.get("/v1/dashboard/research/live")

    assert response.status_code == 200, response.text
    assert response.headers.get("cache-control") == "no-store"


def test_given_anonymous_caller_when_exceeding_30_per_minute_then_excess_is_throttled(
    enable_limiter,
):
    client, _ = _build_client()

    statuses = [
        client.get("/v1/dashboard/research/live").status_code for _ in range(35)
    ]

    success_count = sum(1 for s in statuses if s == 200)
    rate_limited_count = sum(1 for s in statuses if s == 429)
    assert success_count == 30, (
        f"Anonymous quota should be 30/min, got {success_count} successes"
    )
    assert rate_limited_count == 5, (
        f"Expected 5 rate-limited responses, got {rate_limited_count}"
    )


def test_given_authenticated_caller_when_exceeding_300_per_minute_then_excess_is_throttled(
    enable_limiter,
):
    client, api_key = _build_client()
    headers = {"Authorization": f"Bearer {api_key}"}

    statuses = [
        client.get("/v1/dashboard/research/live", headers=headers).status_code
        for _ in range(305)
    ]

    success_count = sum(1 for s in statuses if s == 200)
    rate_limited_count = sum(1 for s in statuses if s == 429)
    assert success_count == 300, (
        f"Authenticated quota should be 300/min, got {success_count} successes"
    )
    assert rate_limited_count == 5, (
        f"Expected 5 rate-limited responses, got {rate_limited_count}"
    )


def test_given_configured_origin_when_browser_makes_request_then_cors_echoes_origin():
    original = app_settings.cors_allow_origins
    app_settings.cors_allow_origins = "https://agentbook.app"
    try:
        client, _ = _build_client()

        response = client.get(
            "/v1/dashboard/research/live",
            headers={"Origin": "https://agentbook.app"},
        )

        assert response.status_code == 200, response.text
        allow_origin = response.headers.get("access-control-allow-origin")
        assert allow_origin == "https://agentbook.app"
        assert allow_origin != "*"
    finally:
        app_settings.cors_allow_origins = original
