from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from backend.domain.models import Outcome, Problem, Solution
from backend.domain.repositories import (
    OutcomeRepository,
    ProblemRepository,
    SolutionRepository,
)
from backend.infrastructure.persistence.in_memory import (
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemorySolutionRepository,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

AUTHOR_ID = UUID("00000000-0000-0000-0000-000000000001")
EMBEDDING_A = [1.0, 0.0, 0.0]
EMBEDDING_B = [0.0, 1.0, 0.0]


def _make_problem(**kwargs) -> Problem:
    return Problem(author_id=AUTHOR_ID, **{"description": "test problem", **kwargs})


def _make_solution(problem_id: UUID, **kwargs) -> Solution:
    return Solution(
        problem_id=problem_id,
        author_id=AUTHOR_ID,
        **{"content": "test solution", **kwargs},
    )


def _make_outcome(
    solution_id: UUID, reporter_id: UUID | None = None, **kwargs
) -> Outcome:
    return Outcome(
        solution_id=solution_id,
        reporter_id=reporter_id or uuid4(),
        success=True,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# ProblemRepository
# ---------------------------------------------------------------------------


def test_problem_add_then_get_returns_same_problem() -> None:
    repo: ProblemRepository = InMemoryProblemRepository()
    problem = _make_problem()

    repo.add(problem)
    result = repo.get(problem.problem_id)

    assert result is problem


def test_problem_get_nonexistent_returns_none() -> None:
    repo: ProblemRepository = InMemoryProblemRepository()

    result = repo.get(uuid4())

    assert result is None


def test_problem_list_all_returns_all_added_problems() -> None:
    repo: ProblemRepository = InMemoryProblemRepository()
    p1 = _make_problem(description="first")
    p2 = _make_problem(description="second")

    repo.add(p1)
    repo.add(p2)
    results = repo.list_all()

    assert len(results) == 2
    ids = {r.problem_id for r in results}
    assert p1.problem_id in ids
    assert p2.problem_id in ids


def test_problem_find_by_error_signature_returns_matching_problem() -> None:
    repo: ProblemRepository = InMemoryProblemRepository()
    problem = _make_problem(error_signature="TypeError: foo is not a function")

    repo.add(problem)
    result = repo.find_by_error_signature("TypeError: foo is not a function")

    assert result is problem


def test_problem_find_by_error_signature_nonexistent_returns_none() -> None:
    repo: ProblemRepository = InMemoryProblemRepository()
    repo.add(_make_problem(error_signature="SomeError"))

    result = repo.find_by_error_signature("nonexistent")

    assert result is None


def test_problem_find_similar_identical_embeddings_returns_problem() -> None:
    repo: ProblemRepository = InMemoryProblemRepository()
    problem = _make_problem(embedding=EMBEDDING_A)

    repo.add(problem)
    results = repo.find_similar(EMBEDDING_A, threshold=0.9)

    assert problem in results


def test_problem_find_similar_orthogonal_embeddings_excluded() -> None:
    repo: ProblemRepository = InMemoryProblemRepository()
    problem = _make_problem(embedding=EMBEDDING_A)

    repo.add(problem)
    # EMBEDDING_B is orthogonal to EMBEDDING_A (cosine similarity == 0.0)
    results = repo.find_similar(EMBEDDING_B, threshold=0.9)

    assert problem not in results


def test_problem_update_persists_changes() -> None:
    repo: ProblemRepository = InMemoryProblemRepository()
    problem = _make_problem()
    repo.add(problem)

    object.__setattr__(problem, "description", "updated description")
    repo.update(problem)
    result = repo.get(problem.problem_id)

    assert result is not None
    assert result.description == "updated description"


# ---------------------------------------------------------------------------
# SolutionRepository
# ---------------------------------------------------------------------------


def test_solution_add_then_get_returns_same_solution() -> None:
    repo: SolutionRepository = InMemorySolutionRepository()
    solution = _make_solution(uuid4())

    repo.add(solution)
    result = repo.get(solution.solution_id)

    assert result is solution


def test_solution_get_nonexistent_returns_none() -> None:
    repo: SolutionRepository = InMemorySolutionRepository()

    result = repo.get(uuid4())

    assert result is None


def test_solution_list_by_problem_returns_solutions_sorted_by_confidence_desc() -> None:
    repo: SolutionRepository = InMemorySolutionRepository()
    problem_id = uuid4()
    low = _make_solution(problem_id, content="low confidence", confidence=0.2)
    high = _make_solution(problem_id, content="high confidence", confidence=0.8)
    mid = _make_solution(problem_id, content="mid confidence", confidence=0.5)

    repo.add(low)
    repo.add(high)
    repo.add(mid)
    results = repo.list_by_problem(problem_id)

    assert len(results) == 3
    assert results[0].solution_id == high.solution_id
    assert results[1].solution_id == mid.solution_id
    assert results[2].solution_id == low.solution_id


def test_solution_list_by_problem_unknown_id_returns_empty_list() -> None:
    repo: SolutionRepository = InMemorySolutionRepository()
    repo.add(_make_solution(uuid4()))

    results = repo.list_by_problem(uuid4())

    assert results == []


def test_solution_update_persists_changes() -> None:
    repo: SolutionRepository = InMemorySolutionRepository()
    solution = _make_solution(uuid4())
    repo.add(solution)

    object.__setattr__(solution, "confidence", 0.95)
    repo.update(solution)
    result = repo.get(solution.solution_id)

    assert result is not None
    assert result.confidence == 0.95


# ---------------------------------------------------------------------------
# OutcomeRepository
# ---------------------------------------------------------------------------


def test_outcome_add_then_list_by_solution_returns_it() -> None:
    repo: OutcomeRepository = InMemoryOutcomeRepository()
    solution_id = uuid4()
    outcome = _make_outcome(solution_id)

    repo.add(outcome)
    results = repo.list_by_solution(solution_id)

    assert outcome in results


def test_outcome_list_by_solution_unknown_id_returns_empty_list() -> None:
    repo: OutcomeRepository = InMemoryOutcomeRepository()
    repo.add(_make_outcome(uuid4()))

    results = repo.list_by_solution(uuid4())

    assert results == []


def test_outcome_count_by_reporter_counts_recent_outcomes() -> None:
    repo: OutcomeRepository = InMemoryOutcomeRepository()
    reporter_id = uuid4()
    since = datetime.now(tz=UTC) - timedelta(hours=1)
    outcome = _make_outcome(uuid4(), reporter_id=reporter_id)

    repo.add(outcome)
    count = repo.count_by_reporter(reporter_id, since=since)

    assert count == 1


def test_outcome_count_by_reporter_since_future_returns_zero() -> None:
    repo: OutcomeRepository = InMemoryOutcomeRepository()
    reporter_id = uuid4()
    outcome = _make_outcome(uuid4(), reporter_id=reporter_id)

    repo.add(outcome)
    future = datetime.now(tz=UTC) + timedelta(hours=1)
    count = repo.count_by_reporter(reporter_id, since=future)

    assert count == 0
