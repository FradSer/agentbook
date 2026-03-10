from __future__ import annotations

from uuid import uuid4

from agent.src.synthesis import find_synthesis_candidates, should_trigger_synthesis
from app.domain.models import Problem, Solution


def make_solution(problem_id=None, **kwargs):
    return Solution(
        problem_id=problem_id or uuid4(),
        author_id=uuid4(),
        content="some solution content",
        **kwargs,
    )


def test_4_similar_solutions_triggers_synthesis():
    solutions = [make_solution() for _ in range(4)]
    matrix = {
        (a.solution_id, b.solution_id): 0.90
        for a in solutions
        for b in solutions
        if a != b
    }
    assert should_trigger_synthesis(solutions, matrix) is True


def test_only_2_similar_solutions_does_not_trigger():
    solutions = [make_solution() for _ in range(2)]
    matrix = {
        (solutions[0].solution_id, solutions[1].solution_id): 0.90,
        (solutions[1].solution_id, solutions[0].solution_id): 0.90,
    }
    assert should_trigger_synthesis(solutions, matrix) is False


def test_10_solutions_always_triggers():
    solutions = [make_solution() for _ in range(10)]
    matrix = {}
    assert should_trigger_synthesis(solutions, matrix) is True


def test_4_solutions_with_low_similarity_does_not_trigger():
    solutions = [make_solution() for _ in range(4)]
    matrix = {
        (a.solution_id, b.solution_id): 0.7
        for a in solutions
        for b in solutions
        if a != b
    }
    assert should_trigger_synthesis(solutions, matrix) is False


def test_low_confidence_high_outcome_count_triggers():
    s = Solution(
        problem_id=uuid4(),
        author_id=uuid4(),
        content="bad solution",
        confidence=0.25,
        outcome_count=10,
        success_count=2,
        failure_count=8,
    )
    assert should_trigger_synthesis([s], {}) is True


def test_find_synthesis_candidates_groups_similar_solutions():
    problem = Problem(author_id=uuid4(), description="test problem")
    solutions = [make_solution(problem.problem_id) for _ in range(3)]

    def sim_fn(a, b):
        return 0.9

    result = find_synthesis_candidates(
        [problem], {problem.problem_id: solutions}, sim_fn
    )
    assert len(result) == 1
    assert len(result[0]) == 3


def test_find_synthesis_candidates_excludes_already_canonical():
    problem = Problem(author_id=uuid4(), description="test problem")
    canonical_sol = make_solution(problem.problem_id, canonical_id=uuid4())
    regular_sols = [make_solution(problem.problem_id) for _ in range(3)]

    def sim_fn(a, b):
        return 0.9

    sols_by_problem = {problem.problem_id: [canonical_sol] + regular_sols}
    result = find_synthesis_candidates([problem], sols_by_problem, sim_fn)
    if result:
        for group in result:
            for s in group:
                assert s.canonical_id is None
