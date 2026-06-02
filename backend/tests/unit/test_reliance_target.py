"""Reliance target is legible across every read surface.

Feature: backend/tests/features/reliance-target.feature

In pre-pilot ``canonical_solution`` is null on essentially every problem (no
synthesis agent has run). Every read surface — GET /v1/problems/{id}, MCP
``trace``, GET /v1/problems/{id}/timeline — must expose a CONSISTENT
``reliance_target`` (the highest-confidence active solution) and self-describe
that it is a cold-start fallback rather than a synthesized canonical entry.
Today the surfaces disagree (``canonical_solution`` vs ``canonical_solution_id``
vs ``book_solution``) so these assertions fail Red until 010-impl unifies them.

Hermetic: in-memory repos, business logic driven directly through
``AgentbookService`` and the MCP dispatcher (no DB, no network).
"""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import pytest

from backend.application.service import AgentbookService
from backend.domain.models import Agent
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)
from backend.presentation.mcp.tools import dispatch_tool


def _service_with_author() -> tuple[AgentbookService, Agent]:
    agents = InMemoryAgentRepository()
    author = Agent(api_key_hash="h", model_type="test", agent_id=uuid4())
    agents.add(author)
    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    return service, author


def _register_reporter(service: AgentbookService) -> Agent:
    reporter = Agent(api_key_hash="h", model_type="test", agent_id=uuid4())
    service._agents.add(reporter)
    return reporter


def _seed_problem_with_two_solutions(
    service: AgentbookService, author: Agent
) -> tuple[object, object, object]:
    """A problem with two active solutions and NO synthesis pass run.

    The second solution is driven above the first by three distinct external
    successes so it is the unambiguous highest-confidence active solution.
    """
    problem = service.create_problem(
        author_id=author.agent_id,
        description="ImportError numpy on Docker Alpine after pip install numpy",
    )
    first = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author.agent_id,
        content="Install build-base and python3-dev via apk before pip install numpy",
    )
    second = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author.agent_id,
        content="Use the official python:3.11-slim image instead of Alpine entirely",
    )
    for _ in range(3):
        reporter = _register_reporter(service)
        service.report_outcome(
            reporter_id=reporter.agent_id,
            solution_id=second.solution_id,
            success=True,
        )
    return problem, first, second


def _trace(service: AgentbookService, problem_id) -> dict:
    server = type("S", (), {})()
    server._service = service
    result = asyncio.run(dispatch_tool(server, "trace", {"id": str(problem_id)}))
    return json.loads(result[0]["text"])


# Scenario: Null canonical surfaces the fallback reliance target in-payload


def test_null_canonical_surfaces_fallback_reliance_target_in_payload() -> None:
    service, author = _service_with_author()
    problem, _first, second = _seed_problem_with_two_solutions(service, author)

    view = service.get_agentbook(problem.problem_id)

    # No synthesis pass has run.
    assert view["canonical_solution"] is None

    target = view["reliance_target"]
    assert target is not None, "GET problem must carry a reliance_target"
    assert target["solution_id"] == str(second.solution_id), (
        "reliance target must be the highest-confidence active solution"
    )
    assert target["is_synthesized"] is False
    note = target.get("note") or view.get("reliance_note")
    assert note, "a fallback note must explain why the target is a fallback"
    assert "highest-confidence active" in note.lower()


# Scenario Outline: The reliance target agrees across every read surface


def _reliance_target_for_surface(service: AgentbookService, problem_id, surface: str):
    if surface == "GET /v1/problems/{id}":
        return service.get_agentbook(problem_id).get("reliance_target")
    if surface == "MCP trace":
        return _trace(service, problem_id).get("reliance_target")
    if surface == "GET /v1/problems/{id}/timeline":
        return service.get_problem_timeline(problem_id).get("reliance_target")
    raise AssertionError(f"unknown surface {surface!r}")


@pytest.mark.parametrize(
    "surface",
    [
        "GET /v1/problems/{id}",
        "MCP trace",
        "GET /v1/problems/{id}/timeline",
    ],
)
def test_reliance_target_agrees_across_every_read_surface(surface: str) -> None:
    service, author = _service_with_author()
    problem, _first, second = _seed_problem_with_two_solutions(service, author)

    target = _reliance_target_for_surface(service, problem.problem_id, surface)

    assert target is not None, f"{surface} did not surface a reliance_target"
    assert target["solution_id"] == str(second.solution_id), (
        f"{surface} surfaced the wrong reliance target"
    )
    # Each surface flags whether the target is synthesized or a fallback.
    assert "is_synthesized" in target, f"{surface} omitted the is_synthesized flag"
    assert target["is_synthesized"] is False


# Scenario: MCP trace exposes the fields the docs promise


def test_mcp_trace_exposes_documented_fields_not_divergent_keys() -> None:
    service, author = _service_with_author()
    problem, _first, _second = _seed_problem_with_two_solutions(service, author)

    payload = _trace(service, problem.problem_id)

    # Documented keys present.
    assert "canonical_solution" in payload, "trace must expose canonical_solution"
    assert payload["canonical_solution"] is None, "null in pre-pilot"
    assert "solution_history" in payload, "trace must expose solution_history"
    assert isinstance(payload["solution_history"], list)
    assert "outcome_summary" in payload, "trace must expose outcome_summary"
    assert isinstance(payload["outcome_summary"], dict)


# Scenario: Read path explains the cold-start floor like the write path does


def test_read_path_explains_cold_start_floor_like_write_path() -> None:
    service, author = _service_with_author()
    problem = service.create_problem(
        author_id=author.agent_id,
        description="Flask app returns 500 on missing CSRF token in form POST",
    )
    sol = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author.agent_id,
        content="Add the csrf_token() hidden input to the form template",
    )
    # The author reports their own perfect success record: confidence stays at
    # the 0.3 baseline because author self-reports never raise confidence.
    service.report_outcome(
        reporter_id=author.agent_id, solution_id=sol.solution_id, success=True
    )
    sol_after = service._solutions.get(sol.solution_id)
    assert sol_after.confidence == pytest.approx(0.3), (
        "this scenario requires the solution to be held at the 0.3 baseline"
    )

    def _note_for(target: dict) -> str:
        assert target is not None
        note = target.get("confidence_note")
        assert note, "reliance target must carry a confidence_note for a 0.3 read"
        return note

    rest_note = _note_for(service.get_agentbook(problem.problem_id)["reliance_target"])
    mcp_note = _note_for(_trace(service, problem.problem_id)["reliance_target"])

    for note in (rest_note, mcp_note):
        assert "0.3" in note, note
        lowered = note.lower()
        assert "external" in lowered, note
        # The note must convey that the author's OWN reports never raise
        # confidence (the cold-start / self-report rule), as the write path does.
        assert "author" in lowered, note
        assert "never move" in lowered or "never raise" in lowered, note
