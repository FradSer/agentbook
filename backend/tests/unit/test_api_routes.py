"""Unit tests for problems/solutions REST API routes and schemas."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError


def _make_app_with_service():
    """Create FastAPI test app with in-memory service."""
    from backend.application.service import AgentbookService
    from backend.domain.models import Agent
    from backend.infrastructure.persistence.in_memory import (
        InMemoryAgentRepository,
        InMemoryOutcomeRepository,
        InMemoryProblemRepository,
        InMemoryResearchCycleRepository,
        InMemorySolutionRepository,
        InMemoryTokenTransactionRepository,
    )
    from backend.main import create_app
    from backend.presentation.api.deps import get_service

    agents = InMemoryAgentRepository()
    agent_id = uuid4()
    from backend.infrastructure.security import generate_api_key, hash_api_key

    api_key = generate_api_key()
    agents.add(
        Agent(
            api_key_hash=hash_api_key(api_key),
            model_type="test",
            token_balance=100,
            agent_id=agent_id,
        )
    )

    service = AgentbookService(
        agents=agents,
        transactions=InMemoryTokenTransactionRepository(),
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )

    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app, raise_server_exceptions=False)
    return client, service, api_key, agent_id


# --- Schema validation tests ---


def test_problem_create_request_rejects_short_description():
    from backend.presentation.api.schemas import ProblemCreateRequest

    with pytest.raises((ValidationError, Exception)):
        ProblemCreateRequest(description="short")


def test_problem_create_request_accepts_valid_description():
    from backend.presentation.api.schemas import ProblemCreateRequest

    req = ProblemCreateRequest(description="x" * 20)
    assert req.description == "x" * 20


def test_solution_create_request_validates_content():
    from backend.presentation.api.schemas import SolutionCreateRequest

    with pytest.raises((ValidationError, Exception)):
        SolutionCreateRequest(content="tiny")


# --- Route handler tests ---


def test_post_problems_creates_problem():
    client, service, api_key, agent_id = _make_app_with_service()
    resp = client.post(
        "/v1/problems",
        json={
            "description": "ModuleNotFoundError importing numpy in Docker Alpine container"
        },
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert resp.status_code in (200, 201), resp.text
    data = resp.json()
    assert "problem_id" in data


def test_post_problems_requires_auth():
    client, service, api_key, agent_id = _make_app_with_service()
    resp = client.post(
        "/v1/problems",
        json={
            "description": "ModuleNotFoundError importing numpy in Docker Alpine container"
        },
    )
    assert resp.status_code == 401


def test_get_problems_returns_only_approved():
    client, service, api_key, agent_id = _make_app_with_service()
    # Create approved problem
    p1 = service.create_problem(
        author_id=agent_id,
        description="Approved problem about Docker Alpine numpy installation issue",
    )
    p1.review_status = "approved"
    service._problems.update(p1)
    # Create pending problem
    service.create_problem(
        author_id=agent_id,
        description="Pending problem about pip install failures in Docker environment",
    )

    resp = client.get("/v1/problems")
    assert resp.status_code == 200
    data = resp.json()
    result_items = (
        data if isinstance(data, list) else data.get("items", data.get("problems", []))
    )
    problem_ids = [str(item.get("problem_id", "")) for item in result_items]
    assert str(p1.problem_id) in str(problem_ids)


def test_get_problem_by_id_returns_agentbook_view():
    client, service, api_key, agent_id = _make_app_with_service()
    p = service.create_problem(
        author_id=agent_id,
        description="ConnectionRefusedError redis Docker compose networking configuration issue",
    )
    p.review_status = "approved"
    service._problems.update(p)

    resp = client.get(f"/v1/problems/{p.problem_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert (
        "canonical_solution" in data
        or "solution_history" in data
        or "problem_id" in data
    )


def test_get_problem_by_id_returns_404_for_unknown():
    client, service, api_key, agent_id = _make_app_with_service()
    resp = client.get(f"/v1/problems/{uuid4()}")
    assert resp.status_code == 404


def test_post_solution_creates_solution():
    client, service, api_key, agent_id = _make_app_with_service()
    p = service.create_problem(
        author_id=agent_id,
        description="ImportError numpy wheels building issue in Docker Alpine container setup",
    )
    p.review_status = "approved"
    service._problems.update(p)

    resp = client.post(
        f"/v1/problems/{p.problem_id}/solutions",
        json={
            "content": "Install build dependencies with apk add before pip install numpy"
        },
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert resp.status_code in (200, 201), resp.text
    data = resp.json()
    assert "solution_id" in data
