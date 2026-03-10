"""Unit tests for AgentbookServiceV2.report_outcome().

BDD scenarios:

Given a solution with 7 successes + 3 failures from distinct reporters
When report_outcome is called with success=True by a new reporter
Then the returned status is "reported" and solution_confidence_updated exceeds 0.70

Given a solution with 7 successes + 3 failures from distinct reporters
When report_outcome is called with success=False by a new reporter
Then solution_confidence_updated drops below 0.70

Given a random solution_id that does not exist in the repository
When report_outcome is called
Then NotFoundError is raised

Given a reporter who has already submitted 10 outcomes in the last hour
When the reporter submits an 11th outcome
Then RateLimitError is raised

Given a fresh solution with no prior outcomes
When report_outcome is called with success=True
Then the solution's outcome_count is 1, success_count is 1, failure_count is 0

Given a problem with a single solution
When report_outcome is called successfully
Then the parent problem's best_confidence is updated above the unverified default
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.application.errors import NotFoundError, RateLimitError
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


def _make_service() -> tuple[
    AgentbookServiceV2,
    InMemoryProblemRepository,
    InMemorySolutionRepository,
    InMemoryOutcomeRepository,
]:
    problems_repo = InMemoryProblemRepository()
    solutions_repo = InMemorySolutionRepository()
    outcomes_repo = InMemoryOutcomeRepository()
    service = AgentbookServiceV2(
        problems=problems_repo,
        solutions=solutions_repo,
        outcomes=outcomes_repo,
    )
    return service, problems_repo, solutions_repo, outcomes_repo


def seed_solution(
    problems_repo: InMemoryProblemRepository,
    solutions_repo: InMemorySolutionRepository,
    author_id: UUID = AUTHOR_ID,
) -> Solution:
    problem = Problem(
        author_id=author_id,
        description="A long enough problem description for testing",
    )
    problems_repo.add(problem)
    solution = Solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="solution content here",
    )
    solutions_repo.add(solution)
    return solution


def _seed_baseline_outcomes(
    outcomes_repo: InMemoryOutcomeRepository,
    solution: Solution,
    *,
    successes: int,
    failures: int,
) -> None:
    """Add outcomes from distinct external reporters (not the solution author)."""
    for _ in range(successes):
        outcomes_repo.add(
            Outcome(
                solution_id=solution.solution_id,
                reporter_id=uuid4(),
                success=True,
            )
        )
    for _ in range(failures):
        outcomes_repo.add(
            Outcome(
                solution_id=solution.solution_id,
                reporter_id=uuid4(),
                success=False,
            )
        )


# ---------------------------------------------------------------------------
# Test 1 — Success report increases confidence
# ---------------------------------------------------------------------------


def test_success_report_increases_confidence_above_baseline() -> None:
    """Given 7+3 baseline, a new success report raises confidence above 0.70."""
    service, problems_repo, solutions_repo, outcomes_repo = _make_service()
    solution = seed_solution(problems_repo, solutions_repo)
    _seed_baseline_outcomes(
        outcomes_repo, solution, successes=7, failures=3
    )

    result = service.report_outcome(
        reporter_id=uuid4(),
        solution_id=solution.solution_id,
        success=True,
    )

    assert result["status"] == "reported"
    assert result["solution_confidence_updated"] > 0.70

    updated_sol = solutions_repo.get(solution.solution_id)
    assert updated_sol is not None
    assert updated_sol.confidence > 0.70


# ---------------------------------------------------------------------------
# Test 2 — Failure report decreases confidence
# ---------------------------------------------------------------------------


def test_failure_report_decreases_confidence_below_baseline() -> None:
    """Given 7+3 baseline, a new failure report lowers confidence below 0.70."""
    service, problems_repo, solutions_repo, outcomes_repo = _make_service()
    solution = seed_solution(problems_repo, solutions_repo)
    _seed_baseline_outcomes(
        outcomes_repo, solution, successes=7, failures=3
    )

    result = service.report_outcome(
        reporter_id=uuid4(),
        solution_id=solution.solution_id,
        success=False,
    )

    assert result["solution_confidence_updated"] < 0.70


# ---------------------------------------------------------------------------
# Test 3 — Solution not found raises NotFoundError
# ---------------------------------------------------------------------------


def test_report_outcome_unknown_solution_raises_not_found() -> None:
    """When solution_id does not exist, NotFoundError is raised."""
    service, _, _, _ = _make_service()

    with pytest.raises(NotFoundError):
        service.report_outcome(
            reporter_id=uuid4(),
            solution_id=uuid4(),
            success=True,
        )


# ---------------------------------------------------------------------------
# Test 4 — Rate limiting (11th outcome in 1 hour from same agent)
# ---------------------------------------------------------------------------


def test_rate_limit_exceeded_after_10_outcomes_in_one_hour() -> None:
    """A reporter submitting more than 10 outcomes within 1 hour is rate-limited."""
    service, problems_repo, solutions_repo, _ = _make_service()
    reporter_id = uuid4()

    for _ in range(10):
        sol = seed_solution(problems_repo, solutions_repo)
        service.report_outcome(
            reporter_id=reporter_id,
            solution_id=sol.solution_id,
            success=True,
        )

    another_sol = seed_solution(problems_repo, solutions_repo)
    with pytest.raises(RateLimitError):
        service.report_outcome(
            reporter_id=reporter_id,
            solution_id=another_sol.solution_id,
            success=True,
        )


# ---------------------------------------------------------------------------
# Test 5 — outcome_count, success_count, failure_count incremented
# ---------------------------------------------------------------------------


def test_outcome_count_incremented_on_solution() -> None:
    """After one success report, outcome_count==1, success_count==1, failure_count==0."""
    service, problems_repo, solutions_repo, _ = _make_service()
    solution = seed_solution(problems_repo, solutions_repo)

    service.report_outcome(
        reporter_id=uuid4(),
        solution_id=solution.solution_id,
        success=True,
    )

    updated_sol = solutions_repo.get(solution.solution_id)
    assert updated_sol is not None
    assert updated_sol.outcome_count == 1
    assert updated_sol.success_count == 1
    assert updated_sol.failure_count == 0


# ---------------------------------------------------------------------------
# Test 6 — best_confidence updated on parent problem
# ---------------------------------------------------------------------------


def test_best_confidence_updated_on_parent_problem() -> None:
    """After a success report, the parent problem's best_confidence increases."""
    service, problems_repo, solutions_repo, _ = _make_service()
    solution = seed_solution(problems_repo, solutions_repo)
    problem_id = solution.problem_id

    service.report_outcome(
        reporter_id=uuid4(),
        solution_id=solution.solution_id,
        success=True,
    )

    problem = problems_repo.get(problem_id)
    assert problem is not None
    assert problem.best_confidence > 0.3
