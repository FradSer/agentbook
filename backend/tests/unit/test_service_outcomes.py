"""Unit tests for AgentbookService outcome reporting."""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.application.errors import RateLimitError


def _make_service():
    from backend.application.service import AgentbookService
    from backend.domain.models import Agent
    from backend.infrastructure.persistence.in_memory import (
        InMemoryAgentRepository,
        InMemoryOutcomeRepository,
        InMemoryProblemRepository,
        InMemoryResearchCycleRepository,
        InMemorySolutionRepository,
    )

    agents = InMemoryAgentRepository()
    alice_id = uuid4()
    bob_id = uuid4()
    agents.add(
        Agent(
            api_key_hash="alice-hash",
            model_type="test",
            agent_id=alice_id,
        )
    )
    agents.add(
        Agent(
            api_key_hash="bob-hash",
            model_type="test",
            agent_id=bob_id,
        )
    )

    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    return service, alice_id, bob_id


def _setup_problem_and_solution(service, alice_id):
    p = service.create_problem(
        author_id=alice_id,
        description="ModuleNotFoundError importing numpy in Docker Alpine container",
    )
    p.review_status = "approved"
    service._problems.update(p)
    s = service.create_solution(
        problem_id=p.problem_id,
        author_id=alice_id,
        content="Install numpy with apk add musl-dev gcc then pip install numpy",
    )
    return p, s


def test_external_reporter_increases_confidence():
    service, alice_id, bob_id = _make_service()
    p, s = _setup_problem_and_solution(service, alice_id)
    initial_confidence = s.confidence

    service.report_outcome(
        reporter_id=bob_id,
        solution_id=s.solution_id,
        success=True,
    )
    updated = service._solutions.get(s.solution_id)
    assert updated.confidence > initial_confidence


def test_outcome_record_created_with_correct_fields():
    service, alice_id, bob_id = _make_service()
    p, s = _setup_problem_and_solution(service, alice_id)

    service.report_outcome(reporter_id=bob_id, solution_id=s.solution_id, success=True)
    updated = service._solutions.get(s.solution_id)
    assert updated.outcome_count == 1
    assert updated.success_count == 1


def test_rate_limit_10_reports_per_hour():
    """Reporter budget is 10 distinct (solution, reporter) outcomes per hour.

    Under v6, repeating a report against the same solution is an
    upsert (no new row), so it cannot consume the budget. The actual
    threat the rate limit guards against is fan-out: one reporter
    voting on many solutions in a short window. We seed 10 solutions
    and confirm the 11th distinct vote is throttled.
    """
    service, alice_id, bob_id = _make_service()
    solutions = [_setup_problem_and_solution(service, alice_id)[1] for _ in range(11)]

    for s in solutions[:10]:
        service.report_outcome(
            reporter_id=bob_id, solution_id=s.solution_id, success=True
        )

    with pytest.raises(RateLimitError):
        service.report_outcome(
            reporter_id=bob_id, solution_id=solutions[10].solution_id, success=True
        )


def test_partial_failure_note_sets_weight_half():
    service, alice_id, bob_id = _make_service()
    p, s = _setup_problem_and_solution(service, alice_id)

    service.report_outcome(
        reporter_id=bob_id,
        solution_id=s.solution_id,
        success=False,
        notes="partial failure — worked for Alpine but not Ubuntu",
    )
    outcomes = service._outcomes.list_by_solution(s.solution_id)
    assert len(outcomes) == 1
    assert outcomes[0].weight == 0.5


def test_self_report_does_not_raise_confidence_above_baseline():
    service, alice_id, bob_id = _make_service()
    p, s = _setup_problem_and_solution(service, alice_id)

    for _ in range(5):
        service.report_outcome(
            reporter_id=alice_id, solution_id=s.solution_id, success=True
        )

    updated = service._solutions.get(s.solution_id)
    assert updated.confidence <= 0.3


def test_external_report_raises_confidence_above_baseline():
    service, alice_id, bob_id = _make_service()
    p, s = _setup_problem_and_solution(service, alice_id)

    service.report_outcome(reporter_id=bob_id, solution_id=s.solution_id, success=True)
    updated = service._solutions.get(s.solution_id)
    assert updated.confidence > 0.3


def test_problem_best_confidence_updated_when_solution_confidence_increases():
    service, alice_id, bob_id = _make_service()
    p, s = _setup_problem_and_solution(service, alice_id)

    service.report_outcome(reporter_id=bob_id, solution_id=s.solution_id, success=True)

    updated_problem = service._problems.get(p.problem_id)
    updated_solution = service._solutions.get(s.solution_id)
    assert updated_problem.best_confidence >= updated_solution.confidence


def test_outcome_count_and_success_count_increment():
    """Distinct reporters each contribute one row; counters track row count.

    Pre-v6 the same reporter could append a fresh outcome on every
    call. Under v6 the second call from ``bob`` would upsert, leaving
    ``outcome_count == 1``. The actual contract — "every distinct
    (solution, reporter) pair adds one outcome" — needs distinct
    reporters to express it.
    """
    from backend.domain.models import Agent

    service, alice_id, bob_id = _make_service()
    p, s = _setup_problem_and_solution(service, alice_id)
    carol_id = uuid4()
    service._agents.add(
        Agent(api_key_hash="carol-hash", model_type="test", agent_id=carol_id)
    )

    service.report_outcome(reporter_id=bob_id, solution_id=s.solution_id, success=True)
    service.report_outcome(
        reporter_id=carol_id, solution_id=s.solution_id, success=False
    )

    updated = service._solutions.get(s.solution_id)
    assert updated.outcome_count == 2
    assert updated.success_count == 1
