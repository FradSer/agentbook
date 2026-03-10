from __future__ import annotations

from uuid import UUID, uuid4

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

AGENT_ID = UUID("00000000-0000-0000-0000-000000000099")


def _make_service(
    problems: InMemoryProblemRepository | None = None,
    solutions: InMemorySolutionRepository | None = None,
    outcomes: InMemoryOutcomeRepository | None = None,
) -> AgentbookServiceV2:
    return AgentbookServiceV2(
        problems=problems or InMemoryProblemRepository(),
        solutions=solutions or InMemorySolutionRepository(),
        outcomes=outcomes or InMemoryOutcomeRepository(),
        embed=None,
    )


def _seed_outcomes(
    solution: Solution,
    outcomes_repo: InMemoryOutcomeRepository,
    count: int,
    success_rate: float,
    author_id: UUID,
) -> None:
    n_success = int(count * success_rate)
    for i in range(count):
        outcome = Outcome(
            solution_id=solution.solution_id,
            reporter_id=uuid4(),
            success=(i < n_success),
        )
        outcomes_repo.add(outcome)


# ---------------------------------------------------------------------------
# Test 1 — Happy path: match found by exact error signature
# ---------------------------------------------------------------------------


def test_resolve_returns_resolved_status_when_error_signature_matches() -> None:
    problems = InMemoryProblemRepository()
    solutions = InMemorySolutionRepository()
    outcomes = InMemoryOutcomeRepository()

    problem = Problem(
        author_id=AGENT_ID,
        description="Pydantic v1 compat import fails on pydantic v2",
        error_signature="ImportError: cannot import 'pydantic.v1'",
    )
    problems.add(problem)

    solution = Solution(
        problem_id=problem.problem_id,
        author_id=AGENT_ID,
        content="Use 'from pydantic.v1 import BaseModel' after upgrading pydantic.",
        confidence=0.75,
    )
    solutions.add(solution)

    service = _make_service(problems=problems, solutions=solutions, outcomes=outcomes)

    result = service.resolve(
        agent_id=AGENT_ID,
        description="pydantic import issue",
        error_signature="ImportError: cannot import 'pydantic.v1'",
        auto_post=True,
    )

    assert result["status"] == "resolved"
    assert len(result["solutions"]) > 0
    for sol in result["solutions"]:
        assert "confidence" in sol


# ---------------------------------------------------------------------------
# Test 2 — No match, auto_post=True → registers new problem
# ---------------------------------------------------------------------------


def test_resolve_registers_problem_when_no_match_and_auto_post_true() -> None:
    problems = InMemoryProblemRepository()
    solutions = InMemorySolutionRepository()
    outcomes = InMemoryOutcomeRepository()

    service = _make_service(problems=problems, solutions=solutions, outcomes=outcomes)

    result = service.resolve(
        agent_id=AGENT_ID,
        description="completely novel error that does not exist anywhere",
        auto_post=True,
    )

    assert result["status"] == "registered"
    assert result["problem_id"] is not None
    assert result["solutions"] == []

    stored = problems.get(result["problem_id"])
    assert stored is not None


# ---------------------------------------------------------------------------
# Test 3 — No match, auto_post=False → no_solutions
# ---------------------------------------------------------------------------


def test_resolve_returns_no_solutions_when_no_match_and_auto_post_false() -> None:
    problems = InMemoryProblemRepository()
    service = _make_service(problems=problems)

    result = service.resolve(
        agent_id=AGENT_ID,
        description="completely novel error with auto_post disabled",
        auto_post=False,
    )

    assert result["status"] == "no_solutions"
    assert problems.list_all() == []


# ---------------------------------------------------------------------------
# Test 4 — Ranking: outcome_rate dominates over similarity
# ---------------------------------------------------------------------------


def test_resolve_ranks_high_outcome_rate_solution_first() -> None:
    problems = InMemoryProblemRepository()
    solutions = InMemorySolutionRepository()
    outcomes = InMemoryOutcomeRepository()

    problem = Problem(
        author_id=AGENT_ID,
        description="Database connection pool exhaustion under load",
        error_signature="OperationalError: pool exhausted",
    )
    problems.add(problem)

    s_low_rate = Solution(
        problem_id=problem.problem_id,
        author_id=AGENT_ID,
        content="Increase pool size in config.",
        confidence=0.55,
        success_count=5,
        failure_count=5,
        outcome_count=10,
    )
    solutions.add(s_low_rate)
    _seed_outcomes(s_low_rate, outcomes, count=10, success_rate=0.50, author_id=AGENT_ID)

    s_high_rate = Solution(
        problem_id=problem.problem_id,
        author_id=AGENT_ID,
        content="Switch to async connection pool with aiopg.",
        confidence=0.70,
        success_count=9,
        failure_count=1,
        outcome_count=10,
    )
    solutions.add(s_high_rate)
    _seed_outcomes(s_high_rate, outcomes, count=10, success_rate=0.90, author_id=AGENT_ID)

    service = _make_service(problems=problems, solutions=solutions, outcomes=outcomes)

    result = service.resolve(
        agent_id=AGENT_ID,
        description="Database connection pool exhaustion under load",
        error_signature="OperationalError: pool exhausted",
        auto_post=True,
    )

    assert result["status"] == "resolved"
    assert len(result["solutions"]) >= 2
    assert result["solutions"][0]["solution_id"] == s_high_rate.solution_id


# ---------------------------------------------------------------------------
# Test 5 — Empty description rejected
# ---------------------------------------------------------------------------


def test_resolve_raises_or_errors_on_empty_description() -> None:
    service = _make_service()

    try:
        result = service.resolve(agent_id=AGENT_ID, description="")
        assert result["status"] == "error"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# Test 6 — Keyword fallback when no error_signature
# ---------------------------------------------------------------------------


def test_resolve_runs_without_error_on_keyword_only_match() -> None:
    problems = InMemoryProblemRepository()
    solutions = InMemorySolutionRepository()
    outcomes = InMemoryOutcomeRepository()

    problem = Problem(
        author_id=AGENT_ID,
        description="pydantic validation error occurs on model creation",
    )
    problems.add(problem)

    solution = Solution(
        problem_id=problem.problem_id,
        author_id=AGENT_ID,
        content="Add validators to your Pydantic model fields.",
    )
    solutions.add(solution)

    service = _make_service(problems=problems, solutions=solutions, outcomes=outcomes)

    result = service.resolve(
        agent_id=AGENT_ID,
        description="pydantic validation issue",
        auto_post=True,
    )

    assert result["status"] in {"resolved", "registered", "no_solutions"}
    assert "solutions" in result
    assert "problem_id" in result
