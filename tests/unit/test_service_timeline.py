"""Unit tests for AgentbookService.get_problem_timeline."""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.application.errors import NotFoundError
from app.domain.models import Agent, Outcome, Problem, ResearchCycle, Solution


def _make_service():
    from app.application.service import AgentbookService
    from app.infrastructure.persistence.in_memory import (
        InMemoryAgentRepository,
        InMemoryOutcomeRepository,
        InMemoryProblemRepository,
        InMemoryResearchCycleRepository,
        InMemorySolutionRepository,
        InMemoryTokenTransactionRepository,
    )

    agents = InMemoryAgentRepository()
    author_id = uuid4()
    agents.add(Agent(api_key_hash="test-hash", model_type="test", token_balance=100, agent_id=author_id))

    service = AgentbookService(
        agents=agents,
        transactions=InMemoryTokenTransactionRepository(),
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    return service, author_id


def _create_approved_problem(service, author_id, description="Test error in Docker"):
    p = service.create_problem(author_id=author_id, description=description)
    p.review_status = "approved"
    service._problems.update(p)
    return p


def _create_approved_solution(service, problem_id, author_id, content="Fix by running apt-get update"):
    s = service.create_solution(problem_id=problem_id, author_id=author_id, content=content)
    s.review_status = "approved"
    service._solutions.update(s)
    return s


def test_get_problem_timeline_raises_not_found():
    service, _ = _make_service()
    with pytest.raises(NotFoundError):
        service.get_problem_timeline(uuid4())


def test_get_problem_timeline_returns_structure():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    result = service.get_problem_timeline(p.problem_id)
    assert "problem" in result
    assert "timeline" in result
    assert result["problem"]["problem_id"] == str(p.problem_id)


def test_timeline_starts_with_problem_created():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    result = service.get_problem_timeline(p.problem_id)
    assert result["timeline"][0]["event_type"] == "problem_created"


def test_timeline_includes_solution_proposed():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    _create_approved_solution(service, p.problem_id, author_id)
    result = service.get_problem_timeline(p.problem_id)
    event_types = [e["event_type"] for e in result["timeline"]]
    assert "solution_proposed" in event_types


def test_timeline_solution_improved_has_parent():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    s = _create_approved_solution(service, p.problem_id, author_id)
    # improve_solution creates a new solution with parent_solution_id set
    long_content = "A" * (len(s.content) * 3)
    service.improve_solution(
        solution_id=s.solution_id,
        improved_content=long_content,
        reasoning="Better approach found",
        author_verified=True,
        author_id=author_id,
    )
    result = service.get_problem_timeline(p.problem_id)
    improved_events = [e for e in result["timeline"] if e["event_type"] == "solution_improved"]
    assert len(improved_events) >= 1
    event = improved_events[0]
    assert event["parent_solution_id"] == str(s.solution_id)


def test_timeline_solution_improved_merges_research_cycle():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    s = _create_approved_solution(service, p.problem_id, author_id)
    long_content = "A" * (len(s.content) * 3)
    service.improve_solution(
        solution_id=s.solution_id,
        improved_content=long_content,
        reasoning="Detailed reasoning here",
        author_verified=True,
        author_id=author_id,
    )
    result = service.get_problem_timeline(p.problem_id)
    improved_events = [e for e in result["timeline"] if e["event_type"] == "solution_improved"]
    assert len(improved_events) >= 1
    event = improved_events[0]
    # ResearchCycle reasoning should be merged into the solution event
    assert "reasoning" in event
    assert "confidence_delta" in event
    assert "previous_best_confidence" in event
    assert "research_status" in event


def test_timeline_research_skipped_only_for_no_proposed():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    # Record a skip (no solution proposed)
    service.record_research_skip(
        problem_id=p.problem_id,
        researcher_id=author_id,
        reasoning="No good improvement found",
        status="no_improvement",
    )
    result = service.get_problem_timeline(p.problem_id)
    skipped_events = [e for e in result["timeline"] if e["event_type"] == "research_skipped"]
    assert len(skipped_events) == 1
    assert skipped_events[0]["reasoning"] == "No good improvement found"


def test_timeline_no_duplicate_for_improved_cycle():
    """When improve_solution produces a cycle with proposed_solution_id, it should
    appear as solution_improved only, not also as research_skipped."""
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    s = _create_approved_solution(service, p.problem_id, author_id)
    long_content = "A" * (len(s.content) * 3)
    service.improve_solution(
        solution_id=s.solution_id,
        improved_content=long_content,
        reasoning="Better approach",
        author_verified=True,
        author_id=author_id,
    )
    result = service.get_problem_timeline(p.problem_id)
    event_types = [e["event_type"] for e in result["timeline"]]
    # research_skipped should not appear for cycles that produced a solution
    assert "research_skipped" not in event_types


def test_timeline_includes_outcome_reported():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    s = _create_approved_solution(service, p.problem_id, author_id)
    reporter_id = uuid4()
    service._agents.add(Agent(api_key_hash="reporter-hash", model_type="test", token_balance=100, agent_id=reporter_id))
    service.report_outcome(
        reporter_id=reporter_id,
        solution_id=s.solution_id,
        success=True,
        notes="Worked great",
    )
    result = service.get_problem_timeline(p.problem_id)
    outcome_events = [e for e in result["timeline"] if e["event_type"] == "outcome_reported"]
    assert len(outcome_events) == 1
    assert outcome_events[0]["success"] is True
    assert outcome_events[0]["solution_id"] == str(s.solution_id)


def test_timeline_is_sorted_ascending():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    _create_approved_solution(service, p.problem_id, author_id)
    result = service.get_problem_timeline(p.problem_id)
    timestamps = [e["created_at"] for e in result["timeline"]]
    assert timestamps == sorted(timestamps)


def test_timeline_promotion_status_included():
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    s = _create_approved_solution(service, p.problem_id, author_id)
    long_content = "A" * (len(s.content) * 3)
    service.improve_solution(
        solution_id=s.solution_id,
        improved_content=long_content,
        reasoning="Better",
        author_verified=True,
        author_id=author_id,
    )
    result = service.get_problem_timeline(p.problem_id)
    improved_events = [e for e in result["timeline"] if e["event_type"] == "solution_improved"]
    assert len(improved_events) >= 1
    # promotion_status should be present (candidate for hill-climbing accepted)
    assert "promotion_status" in improved_events[0]


def test_timeline_synthesis_created_event():
    """synthesize_solutions() should appear as synthesis_created, not solution_proposed."""
    service, author_id = _make_service()
    p = _create_approved_problem(service, author_id)
    _create_approved_solution(service, p.problem_id, author_id, content="Solution A with good detail " * 5)
    _create_approved_solution(service, p.problem_id, author_id, content="Solution B with different approach " * 5)
    service.synthesize_solutions(
        problem_id=p.problem_id,
        synthesized_content="Canonical synthesis combining both approaches " * 5,
        author_id=UUID("00000000-0000-0000-0000-000000000001"),
    )
    result = service.get_problem_timeline(p.problem_id)
    synthesis_events = [e for e in result["timeline"] if e["event_type"] == "synthesis_created"]
    assert len(synthesis_events) == 1
