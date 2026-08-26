"""Verifies features/improving-onboarding.feature.

Every response carries the exact next action: report_hint closes the
recall->report loop in-band; the exact-duplicate refusal carries a prefilled
improve template; successful contributions list their missing knowledge legs.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from backend.application.service import AgentbookService
from backend.domain.models import Agent
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryQueryEventRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)

_DESC = "docker daemon socket permission denied right after install on ubuntu"
_SIG = (
    "permission denied while trying to connect to the docker daemon socket at "
    "unix:///var/run/docker.sock"
)
_QUERY = _SIG


def _service() -> tuple[AgentbookService, UUID]:
    agents = InMemoryAgentRepository()
    author_id = uuid4()
    agents.add(Agent(api_key_hash="h", model_type="test", agent_id=author_id))
    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
        query_events=InMemoryQueryEventRepository(),
    )
    return service, author_id


def _seed_answered(service: AgentbookService, author_id: UUID) -> tuple[UUID, UUID]:
    problem = service.create_problem(
        author_id=author_id, description=_DESC, error_signature=_SIG
    )
    solution = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Add your user to the docker group and start a fresh session.",
        steps=["usermod -aG docker $USER", "newgrp docker"],
        root_cause_pattern="group membership is snapshotted at session start",
        localization_cues=["id -nG output missing docker"],
        verification=[{"command": "docker ps", "expected": "no permission error"}],
    )
    return problem.problem_id, solution.solution_id


# --- report_hint --------------------------------------------------------------


def test_search_match_carries_report_hint() -> None:
    service, author_id = _service()
    pid, sid = _seed_answered(service, author_id)
    payload = service.search_problems(query=_QUERY, limit=5)
    hint = payload.get("report_hint")
    assert hint is not None, "a matched recall must nudge a report"
    assert hint["solution_id"] == str(sid)
    assert "outcomes" in hint["how"]
    assert "report" in hint["how"]
    assert "confidence" in hint["why"]
    # The hint must not leak into per-result rows — it rides top-level only.
    assert all("report_hint" not in row for row in payload["results"])


def test_search_miss_has_no_report_hint() -> None:
    service, author_id = _service()
    _seed_answered(service, author_id)
    payload = service.search_problems(
        query="zzz totally unrelated query about quantum knitting patterns zzz",
        limit=5,
    )
    assert payload.get("report_hint") is None


def test_mcp_recall_parity_for_report_hint() -> None:
    import asyncio
    import json

    from mcp.server import Server

    from backend.presentation.mcp.tools import dispatch_tool

    service, author_id = _service()
    _seed_answered(service, author_id)
    server = Server("parity-test")
    server._service = service
    result = asyncio.run(dispatch_tool(server, "recall", {"query": _QUERY}))
    payload = json.loads(result[0]["text"])
    hint = payload.get("report_hint")
    assert hint is not None
    assert hint["solution_id"] == payload["results"][0]["best_solution"]["solution_id"]


# --- improve_template on duplicate refusal ------------------------------------


def test_duplicate_refusal_carries_prefilled_improve_template() -> None:
    service, author_id = _service()
    pid, sid = _seed_answered(service, author_id)
    result = service.contribute(
        author_id=author_id,
        description=_DESC,
        error_signature=_SIG,
    )
    assert result["status"] == "duplicate_problem"
    template = result.get("improve_template")
    assert template is not None, "refusal must hand the agent its next action"
    assert template["problem_id"] == str(pid)
    assert template["solution_id"] == str(sid)
    assert "/improve" in template["endpoint"]
    assert "improved_content" in template["payload"]


# --- actionability_missing checklist ------------------------------------------


def test_contribute_lists_missing_knowledge_legs() -> None:
    service, author_id = _service()
    problem = service.create_problem(
        author_id=author_id,
        description="Second fixture family for completeness checklist checks",
    )
    result = service.contribute(
        author_id=author_id,
        description=problem.description,
        problem_id=problem.problem_id,
        solution_content="A prose-only fix with no structured knowledge legs.",
        solution_steps=["step one"],
    )
    missing = result["actionability_missing"]
    assert set(missing) == {
        "root_cause_pattern",
        "localization_cues",
        "verification",
    }
    assert "steps" not in missing


def test_fully_armed_contribute_yields_empty_missing_list() -> None:
    service, author_id = _service()
    problem = service.create_problem(
        author_id=author_id,
        description="Third fixture family for completeness checklist checks",
    )
    result = service.contribute(
        author_id=author_id,
        description=problem.description,
        problem_id=problem.problem_id,
        solution_content="Complete fix with every leg attached for parity.",
        solution_steps=["step"],
        solution_root_cause_pattern="pattern",
        solution_localization_cues=["cue"],
        solution_verification=[{"command": "x", "expected": "y"}],
    )
    assert result["actionability_missing"] == []


# --- HTTP-surface regressions (response_model filtering + 409 body) ----------


def test_search_http_surface_keeps_report_hint(client_and_key) -> None:
    """response_model regression guard: SearchResponse must declare
    report_hint or FastAPI strips it (prod lesson 2026-08-26)."""
    from backend.presentation.api.deps import get_service

    client, api_key = client_and_key
    service = client.app.dependency_overrides[get_service]()
    author_id = service.authenticate(api_key, agent_info=None).agent_id
    _seed_answered(service, author_id)

    response = client.get("/v1/search", params={"q": _QUERY, "limit": 3})
    assert response.status_code == 200
    hint = response.json().get("report_hint")
    assert hint is not None
    assert "solution_id" in hint and "/outcomes" in hint["how"]


def test_duplicate_409_body_carries_improve_template(client_and_key) -> None:
    from backend.presentation.api.deps import get_service

    client, api_key = client_and_key
    service = client.app.dependency_overrides[get_service]()
    author_id = service.authenticate(api_key, agent_info=None).agent_id
    _seed_answered(service, author_id)

    response = client.post(
        "/v1/problems",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"description": _DESC, "error_signature": _SIG},
    )
    assert response.status_code == 409
    error = response.json()["error"]
    template = error.get("improve_template")
    assert template is not None
    assert template["problem_id"]
    assert "/improve" in template["endpoint"]
    assert "improved_content" in template["payload"]
