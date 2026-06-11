"""Verifies features/demoted-write-rejection.feature.

A demoted candidate is a rejected dead end (never in solution_history, score
never shown, not re-promotable), so any write targeting it is a wasted,
rate-limited action. These tests pin the fail-loud contract: outcome reports
on a demoted solution are rejected with parent guidance on both transports,
sandbox verification refuses the run, and the common misnamed request fields
(``worked``, ``improvement_reason``) surface guided 422s instead of bare
"Field required" noise.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.presentation.mcp.tools import handle_report

AGENT_ID = uuid4()


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


def _seed_parent_and_demoted(service, author_id):
    problem = service.create_problem(
        author_id=author_id,
        description="ImportError numpy on Docker Alpine container after pip install",
    )
    problem.review_status = "approved"
    service._problems.update(problem)
    parent = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Install build-base and python3-dev via apk before pip install numpy",
    )
    demoted = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Switch the base image to python:3.12-slim and reinstall numpy",
    )
    demoted.parent_solution_id = parent.solution_id
    demoted.promotion_status = "demoted"
    service._solutions.update(demoted)
    return problem, parent, demoted


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# Scenario: Outcome report on a demoted solution is rejected over REST


def test_given_demoted_solution_when_posting_outcome_then_rejected_with_parent_guidance():
    client, service, _, author_id, reporter_key = _make_client()
    _, parent, demoted = _seed_parent_and_demoted(service, author_id)

    response = client.post(
        f"/v1/solutions/{demoted.solution_id}/outcomes",
        json={"success": True},
        headers=_bearer(reporter_key),
    )

    assert response.status_code == 400, response.text
    message = response.json()["error"]["message"]
    assert "demoted" in message
    assert str(parent.solution_id) in message
    assert service._outcomes.list_by_solution(demoted.solution_id) == []


# Scenario: Outcome report rejection has transport parity over MCP


@pytest.mark.asyncio
async def test_report_on_demoted_solution_over_mcp_returns_invalid_input():
    service = MagicMock()
    service.report_outcome.side_effect = ValueError(
        "cannot report an outcome on a demoted solution: the promotion gate rejected it"
    )

    result = await handle_report(
        service,
        AGENT_ID,
        {"solution_id": str(uuid4()), "success": True},
    )

    data = json.loads(result[0]["text"])
    assert data["error"] == "invalid_input"
    assert "demoted" in data["detail"]


# Scenario: Sandbox verification of a demoted solution is refused


def test_given_demoted_solution_when_verifying_then_envelope_is_not_verifiable():
    _, service, _, author_id, _ = _make_client()
    _, _, demoted = _seed_parent_and_demoted(service, author_id)

    result = service.verify_solution(demoted.solution_id, author_id)

    assert result["status"] == "not_verifiable"
    assert "demoted" in result["reason"]


# Scenario: Reports on live solutions are unaffected


def test_given_visible_parent_when_posting_outcome_then_report_is_accepted():
    client, service, _, author_id, reporter_key = _make_client()
    _, parent, _ = _seed_parent_and_demoted(service, author_id)

    response = client.post(
        f"/v1/solutions/{parent.solution_id}/outcomes",
        json={"success": True},
        headers=_bearer(reporter_key),
    )

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "reported"


# Scenario: A misnamed outcome field gets a guided 422


def test_given_worked_field_when_posting_outcome_then_422_points_at_success():
    client, service, _, author_id, reporter_key = _make_client()
    _, parent, _ = _seed_parent_and_demoted(service, author_id)

    response = client.post(
        f"/v1/solutions/{parent.solution_id}/outcomes",
        json={"worked": True},
        headers=_bearer(reporter_key),
    )

    assert response.status_code == 422, response.text
    assert "worked" in response.text
    assert "success" in response.text


@pytest.mark.asyncio
async def test_mcp_report_with_worked_field_names_success_in_detail():
    service = MagicMock()

    result = await handle_report(
        service,
        AGENT_ID,
        {"solution_id": str(uuid4()), "worked": True},
    )

    data = json.loads(result[0]["text"])
    assert data["error"] == "invalid_input"
    assert "worked" in data["detail"]
    assert "success" in data["detail"]
    service.report_outcome.assert_not_called()


# Scenario: A misnamed improve field gets a guided 422


def test_given_improvement_reason_field_when_improving_then_422_points_at_reasoning():
    client, service, _, author_id, reporter_key = _make_client()
    _, parent, _ = _seed_parent_and_demoted(service, author_id)

    response = client.post(
        f"/v1/solutions/{parent.solution_id}/improve",
        json={
            "improved_content": "Pin numpy to a manylinux wheel and drop apk deps",
            "improvement_reason": "wheel avoids the toolchain entirely",
        },
        headers=_bearer(reporter_key),
    )

    assert response.status_code == 422, response.text
    assert "improvement_reason" in response.text
    assert "reasoning" in response.text
