"""Confidence legibility on the outcome-report write contract.

Feature: backend/tests/features/confidence-legibility.feature

An outcome report's response must let an agent read WHY confidence is capped (or
held flat) from structured fields, not only prose: the cold-start floor, the
author-self-report rule, and the external-reporter threshold must be
machine-readable. A re-report must also signal that it replaced the prior report
rather than appending, so a 0.0 delta is never confused with a lost write.

Hermetic: in-memory repos, business logic driven directly through
``AgentbookService`` (no DB, no network).
"""

from __future__ import annotations

from uuid import uuid4

from backend.application.service import AgentbookService
from backend.domain.models import Agent
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)


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


def _seed_solution(service: AgentbookService, author: Agent):
    problem = service.create_problem(
        author_id=author.agent_id,
        description="asyncio task never awaited warning floods the test log output",
    )
    solution = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author.agent_id,
        content="Await the gathered tasks or wrap create_task results in a TaskGroup",
    )
    return solution


# Scenario: Capped report carries machine-readable provenance


def test_capped_report_carries_machine_readable_provenance() -> None:
    service, author = _service_with_author()
    solution = _seed_solution(service, author)

    # First external confirming report (lifts off the baseline).
    first = _register_reporter(service)
    service.report_outcome(
        reporter_id=first.agent_id, solution_id=solution.solution_id, success=True
    )

    # Second external success — still under the 3-reporter threshold, so the
    # score is pinned at the cold-start floor and the delta is 0.0.
    second = _register_reporter(service)
    result = service.report_outcome(
        reporter_id=second.agent_id, solution_id=solution.solution_id, success=True
    )

    assert result["confidence_capped_by"] == "cold_start_floor"
    assert result["external_reporters"] == 2
    assert result["external_reporters_for_full_confidence"] == 3
    assert result["confidence_delta"] == 0.0
    assert "2 of 3 distinct external reporters so far" in result["confidence_note"]


# Scenario: Author self-report is legibly inert


def test_author_self_report_is_legibly_inert() -> None:
    service, author = _service_with_author()
    solution = _seed_solution(service, author)

    result = service.report_outcome(
        reporter_id=author.agent_id, solution_id=solution.solution_id, success=True
    )

    assert result["confidence_delta"] == 0.0
    assert result["external_reporters"] == 0
    note = result["confidence_note"].lower()
    assert "author" in note
    assert "never move" in note or "never raise" in note


# Scenario: Floor release is legible


def test_floor_release_is_legible() -> None:
    service, author = _service_with_author()
    solution = _seed_solution(service, author)

    # Two external confirming reports keep it capped at the floor.
    for _ in range(2):
        reporter = _register_reporter(service)
        service.report_outcome(
            reporter_id=reporter.agent_id,
            solution_id=solution.solution_id,
            success=True,
        )

    capped = service.report_outcome(
        reporter_id=author.agent_id,  # author re-report does not add a reporter
        solution_id=solution.solution_id,
        success=True,
    )
    assert capped["confidence_capped_by"] == "cold_start_floor"

    # The third DISTINCT external reporter releases the floor.
    third = _register_reporter(service)
    result = service.report_outcome(
        reporter_id=third.agent_id, solution_id=solution.solution_id, success=True
    )

    assert result["confidence_capped_by"] is None
    assert result["confidence_delta"] > 0
    assert result["external_reporters"] == 3
    assert (
        result["external_reporters"] >= result["external_reporters_for_full_confidence"]
    )


# Scenario: Re-report signals replace versus append


def test_re_report_signals_replace_versus_append() -> None:
    service, author = _service_with_author()
    solution = _seed_solution(service, author)
    reporter = _register_reporter(service)

    first = service.report_outcome(
        reporter_id=reporter.agent_id, solution_id=solution.solution_id, success=True
    )
    assert first["replaced"] is False

    second = service.report_outcome(
        reporter_id=reporter.agent_id, solution_id=solution.solution_id, success=False
    )
    assert second["replaced"] is True

    # outcome_count stays 1 for that reporter-solution pair (replace, not append).
    outcomes = service._outcomes.list_by_solution(solution.solution_id)
    pair = [o for o in outcomes if o.reporter_id == reporter.agent_id]
    assert len(pair) == 1
    solution_after = service._solutions.get(solution.solution_id)
    assert solution_after.outcome_count == 1
