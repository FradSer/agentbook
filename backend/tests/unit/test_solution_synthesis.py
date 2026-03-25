from __future__ import annotations

from uuid import uuid4

from agent.src.synthesis import _mark_superseded, synthesize_solutions
from backend.domain.models import Problem, Solution


def test_synthesize_solutions_creates_canonical_solution():
    problem = Problem(author_id=uuid4(), description="pydantic v2 migration issues")
    solutions = [
        Solution(
            problem_id=problem.problem_id,
            author_id=uuid4(),
            content=f"solution {i}",
            outcome_count=30,
            success_count=24,
            failure_count=6,
        )
        for i in range(4)
    ]
    def llm_stub(prompt):
        return "Canonical unified solution for pydantic v2 migration"
    canonical = synthesize_solutions(solutions, problem, llm_stub)
    assert canonical.content == "Canonical unified solution for pydantic v2 migration"
    assert canonical.canonical_id is None


def test_synthesize_solutions_inherits_outcome_counts():
    problem = Problem(author_id=uuid4(), description="test problem")
    solutions = [
        Solution(
            problem_id=problem.problem_id,
            author_id=uuid4(),
            content=f"sol {i}",
            outcome_count=30,
            success_count=24,
            failure_count=6,
        )
        for i in range(4)
    ]
    def llm_stub(prompt):
        return "synthesized"
    canonical = synthesize_solutions(solutions, problem, llm_stub)
    assert canonical.outcome_count == 120
    assert canonical.success_count == 96


def test_mark_superseded_sets_canonical_id():
    problem = Problem(author_id=uuid4(), description="test")
    solutions = [
        Solution(
            problem_id=problem.problem_id,
            author_id=uuid4(),
            content=f"sol {i}",
        )
        for i in range(3)
    ]
    canonical_id = uuid4()
    result = _mark_superseded(solutions, canonical_id)
    for s in result:
        assert s.canonical_id == canonical_id


def test_llm_prompt_contains_problem_description():
    problem = Problem(author_id=uuid4(), description="MY UNIQUE PROBLEM DESCRIPTION")
    solutions = [
        Solution(
            problem_id=problem.problem_id,
            author_id=uuid4(),
            content=f"sol {i}",
        )
        for i in range(2)
    ]
    captured_prompt = []

    def llm_stub(prompt):
        captured_prompt.append(prompt)
        return "synthesized content"

    synthesize_solutions(solutions, problem, llm_stub)
    assert "MY UNIQUE PROBLEM DESCRIPTION" in captured_prompt[0]
