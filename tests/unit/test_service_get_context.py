"""Unit tests for AgentbookServiceV2.get_context().

BDD scenarios:

Given a problem with two solutions of different confidence
When get_context is called with include=["solutions"]
Then the result type is "problem", contains both solutions sorted by confidence descending

Given a solution with two outcomes
When get_context is called with include=["outcomes"]
Then the result type is "solution" and contains both outcomes

Given a UUID that does not correspond to any problem or solution
When get_context is called
Then NotFoundError is raised

Given a problem with solutions
When get_context is called with include=["solutions"]
Then "outcomes" and "similar" keys are absent from the result

Given a problem with solutions
When get_context is called with include=None (default)
Then "solutions" key is present in the result
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.application.errors import NotFoundError
from app.application.service_v2 import AgentbookServiceV2
from app.domain.models import Outcome, Problem, Solution
from app.infrastructure.persistence.in_memory_v2 import (
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemorySolutionRepository,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

AUTHOR_ID = UUID("00000000-0000-0000-0000-000000000001")


def make_service() -> tuple[
    AgentbookServiceV2,
    InMemoryProblemRepository,
    InMemorySolutionRepository,
    InMemoryOutcomeRepository,
]:
    problems = InMemoryProblemRepository()
    solutions = InMemorySolutionRepository()
    outcomes = InMemoryOutcomeRepository()
    return AgentbookServiceV2(problems=problems, solutions=solutions, outcomes=outcomes), problems, solutions, outcomes


def _make_problem(**kwargs) -> Problem:
    return Problem(author_id=AUTHOR_ID, **{"description": "test problem", **kwargs})


def _make_solution(problem_id: UUID, **kwargs) -> Solution:
    return Solution(
        problem_id=problem_id,
        author_id=AUTHOR_ID,
        **{"content": "test solution", **kwargs},
    )


def _make_outcome(solution_id: UUID, **kwargs) -> Outcome:
    return Outcome(
        solution_id=solution_id,
        reporter_id=uuid4(),
        success=True,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Test 1 — Fetch problem context with solutions
# ---------------------------------------------------------------------------


def test_get_context_problem_returns_solutions_sorted_by_confidence_desc() -> None:
    """Given a problem with two solutions of different confidence,
    get_context returns type "problem" with solutions sorted descending."""
    service, problems, solutions, _ = make_service()
    p1 = _make_problem()
    problems.add(p1)
    s1 = _make_solution(p1.problem_id, confidence=0.9)
    s2 = _make_solution(p1.problem_id, confidence=0.5)
    solutions.add(s1)
    solutions.add(s2)

    result = service.get_context(id=p1.problem_id, include=["solutions"])

    assert result["type"] == "problem"
    assert result["data"]["problem_id"] == p1.problem_id
    assert len(result["solutions"]) == 2
    assert result["solutions"][0]["confidence"] == 0.9
    assert result["solutions"][1]["confidence"] == 0.5


# ---------------------------------------------------------------------------
# Test 2 — Fetch solution context with outcomes
# ---------------------------------------------------------------------------


def test_get_context_solution_returns_outcomes() -> None:
    """Given a solution with two outcomes,
    get_context returns type "solution" and contains both outcomes."""
    service, problems, solutions, outcomes = make_service()
    p1 = _make_problem()
    problems.add(p1)
    s1 = _make_solution(p1.problem_id)
    solutions.add(s1)
    o1 = _make_outcome(s1.solution_id)
    o2 = _make_outcome(s1.solution_id)
    outcomes.add(o1)
    outcomes.add(o2)

    result = service.get_context(id=s1.solution_id, include=["outcomes"])

    assert result["type"] == "solution"
    assert result["data"]["solution_id"] == s1.solution_id
    assert len(result["outcomes"]) == 2


# ---------------------------------------------------------------------------
# Test 3 — Not found raises NotFoundError
# ---------------------------------------------------------------------------


def test_get_context_unknown_id_raises_not_found_error() -> None:
    """Given a UUID that does not correspond to any problem or solution,
    get_context raises NotFoundError."""
    service, _, _, _ = make_service()

    with pytest.raises(NotFoundError):
        service.get_context(id=uuid4())


# ---------------------------------------------------------------------------
# Test 4 — Include filtering
# ---------------------------------------------------------------------------


def test_get_context_include_solutions_excludes_other_sections() -> None:
    """Given a problem with solutions,
    when include=["solutions"] then "outcomes" and "similar" are absent."""
    service, problems, solutions, _ = make_service()
    p1 = _make_problem()
    problems.add(p1)
    s1 = _make_solution(p1.problem_id, confidence=0.7)
    solutions.add(s1)

    result_solutions_only = service.get_context(id=p1.problem_id, include=["solutions"])

    assert "outcomes" not in result_solutions_only
    assert "similar" not in result_solutions_only


def test_get_context_empty_include_does_not_crash_and_has_type() -> None:
    """Given a problem, when include=[] the call does not crash and 'type' is present."""
    service, problems, _, _ = make_service()
    p1 = _make_problem()
    problems.add(p1)

    result_empty_include = service.get_context(id=p1.problem_id, include=[])

    assert "type" in result_empty_include


# ---------------------------------------------------------------------------
# Test 5 — Default include (None means all sections)
# ---------------------------------------------------------------------------


def test_get_context_default_include_none_includes_solutions_for_problem() -> None:
    """Given a problem with solutions, when include=None then 'solutions' is present."""
    service, problems, solutions, _ = make_service()
    p1 = _make_problem()
    problems.add(p1)
    s1 = _make_solution(p1.problem_id, confidence=0.6)
    solutions.add(s1)

    result = service.get_context(id=p1.problem_id)

    assert "solutions" in result


# ---------------------------------------------------------------------------
# Test 6 — Solutions in context sorted by confidence
# ---------------------------------------------------------------------------


def test_get_context_solutions_sorted_by_confidence_descending() -> None:
    """Given a problem with multiple solutions of varied confidence,
    the solutions list is sorted by confidence descending."""
    service, problems, solutions, _ = make_service()
    p1 = _make_problem()
    problems.add(p1)
    for conf in [0.4, 0.9, 0.1, 0.7]:
        solutions.add(_make_solution(p1.problem_id, confidence=conf))

    result = service.get_context(id=p1.problem_id, include=["solutions"])

    confidences = [s["confidence"] for s in result["solutions"]]
    assert confidences == sorted(confidences, reverse=True)
