"""Unit tests for problem-level outcome_summary aggregation.

Feature: backend/tests/features/outcome-summary.feature

outcome_summary at the problem level must aggregate outcomes across ALL of a
problem's visible solutions, not just the single highest-confidence one — so a
non-top solution's failure is not invisible in the headline metric. All
hermetic: in-memory repos, business logic exercised directly through
``AgentbookService``.
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


def _seed_problem_with_two_solutions(
    service: AgentbookService, author: Agent
) -> tuple[object, object, object]:
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
    return problem, first, second


# Scenario: Two solutions each with one outcome sum to two


def test_two_solutions_each_with_one_success_sum_to_two() -> None:
    service, author = _service_with_author()
    problem, first, second = _seed_problem_with_two_solutions(service, author)

    reporter_a = _register_reporter(service)
    reporter_b = _register_reporter(service)
    service.report_outcome(
        reporter_id=reporter_a.agent_id, solution_id=first.solution_id, success=True
    )
    service.report_outcome(
        reporter_id=reporter_b.agent_id, solution_id=second.solution_id, success=True
    )

    view = service.get_agentbook(problem.problem_id)
    summary = view["outcome_summary"]

    assert summary["total"] == 2, summary
    assert summary["successes"] == 2, summary

    # The headline metric must agree with the timeline's outcome events.
    timeline = service.get_problem_timeline(problem.problem_id)
    reported_events = [
        e for e in timeline["timeline"] if e["event_type"] == "outcome_reported"
    ]
    assert len(reported_events) == summary["total"]


# Scenario: Summary tracks failures on a non-top solution


def test_failure_on_non_top_solution_is_visible_in_headline() -> None:
    service, author = _service_with_author()
    problem, top, second = _seed_problem_with_two_solutions(service, author)

    # Drive the top solution above baseline so it is the highest-confidence
    # (top) solution, then record a failure on the *other* solution.
    for _ in range(3):
        reporter = _register_reporter(service)
        service.report_outcome(
            reporter_id=reporter.agent_id,
            solution_id=top.solution_id,
            success=True,
        )
    failure_reporter = _register_reporter(service)
    service.report_outcome(
        reporter_id=failure_reporter.agent_id,
        solution_id=second.solution_id,
        success=False,
        notes="Slim image still missing gfortran for scipy co-install",
    )

    top_after = service._solutions.get(top.solution_id)
    second_after = service._solutions.get(second.solution_id)
    assert top_after.confidence >= second_after.confidence, (
        "the success-laden solution must be the top one for this scenario"
    )

    summary = service.get_agentbook(problem.problem_id)["outcome_summary"]

    assert summary["total"] == 4, summary
    assert summary["successes"] == 3, summary
    assert summary["failures"] == 1, summary
    assert any("gfortran" in note for note in summary["recent_failure_notes"]), summary
