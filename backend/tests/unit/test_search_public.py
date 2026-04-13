"""Public-read REST search contract.

After the public-memory pivot, GET /v1/search must work without an
Authorization header. Writes (POST /v1/problems) still require auth.
"""

from __future__ import annotations

from uuid import uuid4

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


def test_search_returns_200_without_authorization_header():
    client, _ = _make_client()
    response = client.get("/v1/search", params={"q": "hydration error"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert "results" in body
    assert "total" in body


def test_search_returns_same_shape_with_and_without_auth():
    client, api_key = _make_client()

    anon = client.get("/v1/search", params={"q": "module not found"})
    auth = client.get(
        "/v1/search",
        params={"q": "module not found"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert anon.status_code == 200
    assert auth.status_code == 200
    assert set(anon.json().keys()) == set(auth.json().keys())


def test_post_problems_still_requires_authorization():
    client, _ = _make_client()
    response = client.post(
        "/v1/problems",
        json={
            "description": "ModuleNotFoundError importing numpy in Docker Alpine container"
        },
    )
    assert response.status_code == 401, response.text


def test_post_problems_succeeds_with_valid_authorization():
    client, api_key = _make_client()
    response = client.post(
        "/v1/problems",
        json={
            "description": "ModuleNotFoundError importing numpy in Docker Alpine container"
        },
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert response.status_code in (200, 201), response.text
