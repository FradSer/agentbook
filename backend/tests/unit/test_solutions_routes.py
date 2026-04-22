"""HTTP-level contract tests for the solutions router and problem timeline.

Covers the cross-layer paths that were dropped when the legacy integration
tests (test_api_flow.py, test_api_errors.py) were deleted. These tests go
through the full FastAPI stack via TestClient with in-memory repositories.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


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
    author_key = generate_api_key()
    author_id = uuid4()
    agents.add(
        Agent(
            api_key_hash=hash_api_key(author_key),
            model_type="test",
            agent_id=author_id,
        )
    )
    reporter_key = generate_api_key()
    reporter_id = uuid4()
    agents.add(
        Agent(
            api_key_hash=hash_api_key(reporter_key),
            model_type="test",
            agent_id=reporter_id,
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
    client = TestClient(app, raise_server_exceptions=False)
    return client, service, author_key, author_id, reporter_key


def _seed_problem_and_solution(service, author_id):
    problem = service.create_problem(
        author_id=author_id,
        description="ImportError numpy on Docker Alpine container after pip install",
    )
    problem.review_status = "approved"
    service._problems.update(problem)
    solution = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Install build-base and python3-dev via apk before pip install numpy",
    )
    return problem, solution


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# POST /v1/solutions/{id}/outcomes


def test_given_authenticated_external_reporter_when_posting_outcome_then_response_is_created_and_confidence_is_updated():
    client, service, _, author_id, reporter_key = _make_client()
    _, solution = _seed_problem_and_solution(service, author_id)

    response = client.post(
        f"/v1/solutions/{solution.solution_id}/outcomes",
        json={"success": True},
        headers=_bearer(reporter_key),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "reported"
    assert body["solution_confidence_updated"] > 0.3


def test_given_outcome_endpoint_when_authorization_is_missing_then_response_is_unauthorized():
    client, service, _, author_id, _ = _make_client()
    _, solution = _seed_problem_and_solution(service, author_id)

    response = client.post(
        f"/v1/solutions/{solution.solution_id}/outcomes",
        json={"success": True},
    )

    assert response.status_code == 401


def test_given_outcome_endpoint_rate_limit_budget_when_exceeded_then_response_is_throttled():
    client, service, _, author_id, reporter_key = _make_client()
    _, solution = _seed_problem_and_solution(service, author_id)
    headers = _bearer(reporter_key)

    for _ in range(10):
        ok = client.post(
            f"/v1/solutions/{solution.solution_id}/outcomes",
            json={"success": True},
            headers=headers,
        )
        assert ok.status_code == 201, ok.text

    limited = client.post(
        f"/v1/solutions/{solution.solution_id}/outcomes",
        json={"success": True},
        headers=headers,
    )
    assert limited.status_code == 429


# POST /v1/solutions/{id}/improve


def test_given_authorized_author_when_posting_improvement_then_improvement_response_fields_are_present():
    client, service, author_key, author_id, _ = _make_client()
    _, solution = _seed_problem_and_solution(service, author_id)

    response = client.post(
        f"/v1/solutions/{solution.solution_id}/improve",
        json={
            "improved_content": (
                "Install build-base, python3-dev and gfortran via apk, "
                "then pip install numpy with --no-cache-dir to avoid wheel bloat."
            ),
            "reasoning": "Adds missing gfortran for scipy co-installs",
        },
        headers=_bearer(author_key),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert "status" in body
    assert "new_confidence" in body
    assert "previous_confidence" in body


def test_given_improve_endpoint_when_authorization_is_missing_then_response_is_unauthorized():
    client, service, _, author_id, _ = _make_client()
    _, solution = _seed_problem_and_solution(service, author_id)

    response = client.post(
        f"/v1/solutions/{solution.solution_id}/improve",
        json={
            "improved_content": "x" * 40,
            "reasoning": "no auth",
        },
    )

    assert response.status_code == 401


# GET /v1/solutions/{id}/lineage


def test_given_solution_lineage_endpoint_when_fetching_known_solution_then_public_lineage_list_is_returned():
    client, service, _, author_id, _ = _make_client()
    _, solution = _seed_problem_and_solution(service, author_id)

    response = client.get(f"/v1/solutions/{solution.solution_id}/lineage")

    assert response.status_code == 200, response.text
    body = response.json()
    assert "lineage" in body
    assert isinstance(body["lineage"], list)


# GET /v1/problems/{id}/timeline — route ordering guard


def test_given_problem_timeline_route_when_requesting_timeline_then_specific_timeline_handler_wins_over_generic_problem_route():
    """CLAUDE.md mandates /problems/{id}/timeline be registered before /problems/{id}.

    If the ordering regresses, a timeline request would get matched by the
    AgentbookView handler and return the wrong shape. This test guards that.
    """
    client, service, _, author_id, _ = _make_client()
    problem, _ = _seed_problem_and_solution(service, author_id)

    response = client.get(f"/v1/problems/{problem.problem_id}/timeline")

    assert response.status_code == 200, response.text
    body = response.json()
    assert "timeline" in body
    assert "problem" in body
    assert body["problem"]["problem_id"] == str(problem.problem_id)


# POST /v1/problems/{id}/solutions — 404 when parent problem is missing


@pytest.mark.parametrize(
    ("route_template", "method", "payload", "needs_auth"),
    [
        ("/v1/solutions/{id}/outcomes", "post", {"success": True}, True),
        ("/v1/solutions/{id}/lineage", "get", None, False),
        ("/v1/problems/{id}/timeline", "get", None, False),
        (
            "/v1/problems/{id}/solutions",
            "post",
            {"content": "Install build-base via apk then pip install numpy"},
            True,
        ),
    ],
)
def test_given_unknown_resource_id_when_calling_route_then_response_is_not_found(
    route_template: str,
    method: str,
    payload: dict | None,
    needs_auth: bool,
):
    client, _, author_key, _, reporter_key = _make_client()
    resource_id = uuid4()
    url = route_template.format(id=resource_id)
    headers = {}
    if needs_auth:
        headers = (
            _bearer(reporter_key)
            if route_template.endswith("/outcomes")
            else _bearer(author_key)
        )
    response = client.request(method.upper(), url, json=payload, headers=headers)
    assert response.status_code == 404


# ProblemCreateRequest 422 validation at the HTTP layer


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        ({"description": "too short"}, 422),  # < 20 chars
        ({}, 422),  # missing description
    ],
)
def test_post_problem_validation_errors(payload, expected_code):
    client, _, author_key, _, _ = _make_client()

    response = client.post(
        "/v1/problems",
        json=payload,
        headers=_bearer(author_key),
    )

    assert response.status_code == expected_code
