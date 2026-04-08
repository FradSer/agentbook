"""Unit tests for AgentbookService outcome reporting and token economy."""

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
        InMemoryTokenTransactionRepository,
    )

    agents = InMemoryAgentRepository()
    alice_id = uuid4()
    bob_id = uuid4()
    agents.add(
        Agent(
            api_key_hash="alice-hash",
            model_type="test",
            token_balance=100,
            agent_id=alice_id,
        )
    )
    agents.add(
        Agent(
            api_key_hash="bob-hash",
            model_type="test",
            token_balance=100,
            agent_id=bob_id,
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
    service, alice_id, bob_id = _make_service()
    p, s = _setup_problem_and_solution(service, alice_id)

    for _ in range(10):
        service.report_outcome(
            reporter_id=bob_id, solution_id=s.solution_id, success=True
        )

    with pytest.raises(RateLimitError):
        service.report_outcome(
            reporter_id=bob_id, solution_id=s.solution_id, success=True
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


def test_token_reward_issued_on_successful_external_outcome():
    service, alice_id, bob_id = _make_service()
    p, s = _setup_problem_and_solution(service, alice_id)

    alice_before = service._agents.get(alice_id).token_balance
    result = service.report_outcome(
        reporter_id=bob_id, solution_id=s.solution_id, success=True
    )

    alice_after = service._agents.get(alice_id).token_balance
    assert alice_after > alice_before
    assert result.get("reward_issued") is True


def test_no_token_reward_on_failed_outcome():
    service, alice_id, bob_id = _make_service()
    p, s = _setup_problem_and_solution(service, alice_id)

    alice_before = service._agents.get(alice_id).token_balance
    result = service.report_outcome(
        reporter_id=bob_id, solution_id=s.solution_id, success=False
    )

    alice_after = service._agents.get(alice_id).token_balance
    assert alice_after == alice_before
    assert result.get("reward_issued") is False


def test_no_self_reward_when_author_reports_own_outcome():
    service, alice_id, bob_id = _make_service()
    p, s = _setup_problem_and_solution(service, alice_id)

    alice_before = service._agents.get(alice_id).token_balance
    result = service.report_outcome(
        reporter_id=alice_id, solution_id=s.solution_id, success=True
    )

    alice_after = service._agents.get(alice_id).token_balance
    assert alice_after == alice_before
    assert result.get("reward_issued") is False


def test_problem_best_confidence_updated_when_solution_confidence_increases():
    service, alice_id, bob_id = _make_service()
    p, s = _setup_problem_and_solution(service, alice_id)

    service.report_outcome(reporter_id=bob_id, solution_id=s.solution_id, success=True)

    updated_problem = service._problems.get(p.problem_id)
    updated_solution = service._solutions.get(s.solution_id)
    assert updated_problem.best_confidence >= updated_solution.confidence


def test_outcome_count_and_success_count_increment():
    service, alice_id, bob_id = _make_service()
    p, s = _setup_problem_and_solution(service, alice_id)

    service.report_outcome(reporter_id=bob_id, solution_id=s.solution_id, success=True)
    service.report_outcome(reporter_id=bob_id, solution_id=s.solution_id, success=False)

    updated = service._solutions.get(s.solution_id)
    assert updated.outcome_count == 2
    assert updated.success_count == 1
