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


# POST /v1/solutions/{id}/outcomes


def test_post_outcome_succeeds_with_external_reporter():
    client, service, _, author_id, reporter_key = _make_client()
    _, solution = _seed_problem_and_solution(service, author_id)

    response = client.post(
        f"/v1/solutions/{solution.solution_id}/outcomes",
        json={"success": True},
        headers={"Authorization": f"Bearer {reporter_key}"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "reported"
    assert body["solution_confidence_updated"] > 0.3


def test_post_outcome_requires_authorization():
    client, service, _, author_id, _ = _make_client()
    _, solution = _seed_problem_and_solution(service, author_id)

    response = client.post(
        f"/v1/solutions/{solution.solution_id}/outcomes",
        json={"success": True},
    )

    assert response.status_code == 401


def test_post_outcome_on_unknown_solution_returns_404():
    client, _, _, _, reporter_key = _make_client()

    response = client.post(
        f"/v1/solutions/{uuid4()}/outcomes",
        json={"success": True},
        headers={"Authorization": f"Bearer {reporter_key}"},
    )

    assert response.status_code == 404


def test_post_outcome_rate_limit_returns_429():
    client, service, _, author_id, reporter_key = _make_client()
    _, solution = _seed_problem_and_solution(service, author_id)
    headers = {"Authorization": f"Bearer {reporter_key}"}

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


def test_post_improve_succeeds_with_auth():
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
        headers={"Authorization": f"Bearer {author_key}"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert "status" in body
    assert "new_confidence" in body
    assert "previous_confidence" in body


def test_post_improve_requires_authorization():
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


def test_get_solution_lineage_is_public_and_returns_list():
    client, service, _, author_id, _ = _make_client()
    _, solution = _seed_problem_and_solution(service, author_id)

    response = client.get(f"/v1/solutions/{solution.solution_id}/lineage")

    assert response.status_code == 200, response.text
    body = response.json()
    assert "lineage" in body
    assert isinstance(body["lineage"], list)


def test_get_solution_lineage_unknown_returns_404():
    client, *_ = _make_client()

    response = client.get(f"/v1/solutions/{uuid4()}/lineage")

    assert response.status_code == 404


# GET /v1/problems/{id}/timeline — route ordering guard


def test_problem_timeline_route_wins_over_generic_problem_route():
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


def test_problem_timeline_unknown_returns_404():
    client, *_ = _make_client()

    response = client.get(f"/v1/problems/{uuid4()}/timeline")

    assert response.status_code == 404


# POST /v1/problems/{id}/solutions — 404 when parent problem is missing


def test_post_solution_on_unknown_problem_returns_404():
    client, _, author_key, _, _ = _make_client()

    response = client.post(
        f"/v1/problems/{uuid4()}/solutions",
        json={"content": "Install build-base via apk then pip install numpy"},
        headers={"Authorization": f"Bearer {author_key}"},
    )

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
        headers={"Authorization": f"Bearer {author_key}"},
    )

    assert response.status_code == expected_code
