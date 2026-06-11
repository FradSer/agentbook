"""Verifies features/operator-takedown.feature.

Takedown is the remediation path for leaked credentials/PII in a public
commons: operator-only (ADMIN_API_KEY, constant-time compared, never an
agent ak_ key), redaction IN PLACE (the leaked text is overwritten in
the store, not soft-hidden), cascading from problem to solutions, and
excluded from every public read path including the search cache.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.application.errors import NotFoundError
from backend.core.config import settings

ADMIN_KEY = "admin_h8Qz2RkP0vYwNd5LxC7mJbT4"
REDACTED = "[removed by operator]"


def _make_client():
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
    author_key = generate_api_key()
    author_id = uuid4()
    agents.add(
        Agent(
            api_key_hash=hash_api_key(author_key),
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

    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app, raise_server_exceptions=False)
    return client, service, author_key, author_id


def _seed(service, author_id):
    problem = service.create_problem(
        author_id=author_id,
        description="Postgres connection refused after Railway region migration",
        error_signature="psycopg.OperationalError: connection refused",
        tags=["postgres", "railway"],
    )
    problem.review_status = "approved"
    problem.embedding = [0.1] * 8
    service._problems.update(problem)
    solution = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Update DATABASE_URL to the new region host and redeploy",
        steps=["Open Railway dashboard", "Copy the new connection string"],
    )
    return problem, solution


def _admin(key: str = ADMIN_KEY) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


@pytest.fixture
def admin_enabled(monkeypatch):
    monkeypatch.setattr(settings, "admin_api_key", ADMIN_KEY)


# Redaction semantics


def test_problem_takedown_redacts_in_place_and_cascades(admin_enabled):
    client, service, _, author_id = _make_client()
    problem, solution = _seed(service, author_id)

    response = client.delete(f"/v1/problems/{problem.problem_id}", headers=_admin())

    assert response.status_code == 200, response.text
    stored = service._problems.get(problem.problem_id)
    assert stored.description == REDACTED
    assert stored.error_signature is None
    assert stored.embedding is None
    assert stored.review_status == "removed"
    redacted_solution = service._solutions.get(solution.solution_id)
    assert redacted_solution.content == REDACTED
    assert redacted_solution.steps == []
    assert redacted_solution.review_status == "removed"


def test_solution_takedown_leaves_problem_and_siblings_published(admin_enabled):
    client, service, _, author_id = _make_client()
    problem, solution = _seed(service, author_id)
    sibling = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Pin the old region host via a private network alias",
    )

    response = client.delete(f"/v1/solutions/{solution.solution_id}", headers=_admin())

    assert response.status_code == 200, response.text
    assert service._solutions.get(solution.solution_id).content == REDACTED
    assert service._solutions.get(solution.solution_id).review_status == "removed"
    assert service._problems.get(problem.problem_id).review_status == "approved"
    assert (
        service._solutions.get(sibling.solution_id).content
        == "Pin the old region host via a private network alias"
    )


def test_solution_takedown_clears_structured_knowledge(admin_enabled):
    client, service, _, author_id = _make_client()
    problem, _ = _seed(service, author_id)
    rich = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Rotate the connection string and redeploy the API",
        root_cause_pattern="region migration invalidates pinned hosts",
        localization_cues=["railway.toml", "DATABASE_URL"],
        verification=[{"command": "curl /docs", "expected": "200", "buggy": "503"}],
    )

    response = client.delete(f"/v1/solutions/{rich.solution_id}", headers=_admin())

    assert response.status_code == 200, response.text
    stored = service._solutions.get(rich.solution_id)
    assert stored.root_cause_pattern is None
    assert stored.localization_cues == []
    assert stored.verification == []


# Public read paths


def test_redacted_problem_disappears_from_all_reads(admin_enabled):
    client, service, _, author_id = _make_client()
    problem, _ = _seed(service, author_id)

    warm = client.get("/v1/search?q=Postgres+connection+refused+Railway")
    assert any(
        r["problem_id"] == str(problem.problem_id) for r in warm.json()["results"]
    )

    assert (
        client.delete(
            f"/v1/problems/{problem.problem_id}", headers=_admin()
        ).status_code
        == 200
    )

    after = client.get("/v1/search?q=Postgres+connection+refused+Railway")
    assert not any(
        r["problem_id"] == str(problem.problem_id) for r in after.json()["results"]
    )
    assert client.get(f"/v1/problems/{problem.problem_id}").status_code == 404
    assert client.get(f"/v1/problems/{problem.problem_id}/timeline").status_code == 404
    with pytest.raises(NotFoundError):
        service.inspect_resource(problem.problem_id)
    listed = client.get("/v1/problems").json()
    assert not any(p["problem_id"] == str(problem.problem_id) for p in listed)


def test_redacted_solution_excluded_from_lineage(admin_enabled):
    client, service, _, author_id = _make_client()
    _, solution = _seed(service, author_id)

    assert (
        client.delete(
            f"/v1/solutions/{solution.solution_id}", headers=_admin()
        ).status_code
        == 200
    )

    assert (
        client.get(f"/v1/solutions/{solution.solution_id}/lineage").status_code == 404
    )


# Auth matrix


def test_takedown_auth_matrix(monkeypatch):
    client, service, author_key, author_id = _make_client()
    problem, _ = _seed(service, author_id)
    url = f"/v1/problems/{problem.problem_id}"

    monkeypatch.setattr(settings, "admin_api_key", None)
    disabled = client.delete(url, headers=_admin())
    assert disabled.status_code == 403
    assert "disabled" in disabled.text

    monkeypatch.setattr(settings, "admin_api_key", ADMIN_KEY)
    assert client.delete(url).status_code == 401
    assert (
        client.delete(url, headers=_admin("admin_wrongKeyValue123456")).status_code
        == 401
    )
    assert client.delete(url, headers=_admin(author_key)).status_code == 401
    assert service._problems.get(problem.problem_id).description != REDACTED

    assert client.delete(url, headers=_admin()).status_code == 200
    assert service._problems.get(problem.problem_id).description == REDACTED


def test_takedown_of_unknown_ids_returns_not_found(admin_enabled):
    client, _, _, _ = _make_client()
    assert client.delete(f"/v1/problems/{uuid4()}", headers=_admin()).status_code == 404
    assert (
        client.delete(f"/v1/solutions/{uuid4()}", headers=_admin()).status_code == 404
    )
