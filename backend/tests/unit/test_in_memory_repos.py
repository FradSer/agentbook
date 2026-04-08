"""Unit tests for in-memory repository implementations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4


def _make_problem(**kwargs):
    from backend.domain.models import Problem

    defaults = dict(
        author_id=uuid4(), description="Test problem description that is long enough"
    )
    defaults.update(kwargs)
    return Problem(**defaults)


def _make_solution(problem_id=None, **kwargs):
    from backend.domain.models import Solution

    defaults = dict(
        problem_id=problem_id or uuid4(),
        author_id=uuid4(),
        content="Fix the issue by running the command",
    )
    defaults.update(kwargs)
    return Solution(**defaults)


# ---------------------------------------------------------------------------
# InMemoryProblemRepository tests
# ---------------------------------------------------------------------------


def test_problem_repo_add_and_get():
    from backend.infrastructure.persistence.in_memory import InMemoryProblemRepository

    repo = InMemoryProblemRepository()
    p = _make_problem()
    repo.add(p)
    assert repo.get(p.problem_id) == p


def test_problem_repo_delete_removes_problem():
    from backend.infrastructure.persistence.in_memory import InMemoryProblemRepository

    repo = InMemoryProblemRepository()
    p = _make_problem()
    repo.add(p)
    repo.delete(p.problem_id)
    assert repo.get(p.problem_id) is None


def test_problem_repo_find_unreviewed_returns_none_status():
    from backend.infrastructure.persistence.in_memory import InMemoryProblemRepository

    repo = InMemoryProblemRepository()
    p_pending = _make_problem()
    p_approved = _make_problem()
    p_approved.review_status = "approved"

    repo.add(p_pending)
    repo.add(p_approved)

    results = repo.find_unreviewed(limit=10)
    ids = [r.problem_id for r in results]
    assert p_pending.problem_id in ids
    assert p_approved.problem_id not in ids


def test_problem_repo_find_unreviewed_includes_error_with_cutoff():
    from backend.infrastructure.persistence.in_memory import InMemoryProblemRepository

    repo = InMemoryProblemRepository()
    p_error = _make_problem()
    p_error.review_status = "error"

    repo.add(p_error)

    # Without cutoff, error-status problems are excluded
    no_cutoff = repo.find_unreviewed(limit=10)
    assert p_error.problem_id not in [r.problem_id for r in no_cutoff]

    # With cutoff in the future, error problems are retried
    cutoff = datetime.now(tz=UTC) + timedelta(seconds=1)
    with_cutoff = repo.find_unreviewed(limit=10, retry_error_before=cutoff)
    assert p_error.problem_id in [r.problem_id for r in with_cutoff]


def test_problem_repo_find_research_candidates_low_confidence():
    from backend.infrastructure.persistence.in_memory import InMemoryProblemRepository

    repo = InMemoryProblemRepository()
    low_conf = _make_problem()
    low_conf.best_confidence = 0.2
    low_conf.solution_count = 1
    low_conf.review_status = "approved"

    high_conf = _make_problem()
    high_conf.best_confidence = 0.9
    high_conf.solution_count = 1
    high_conf.review_status = "approved"

    repo.add(low_conf)
    repo.add(high_conf)

    candidates = repo.find_research_candidates(limit=10)
    ids = [c.problem_id for c in candidates]
    assert low_conf.problem_id in ids


def test_problem_repo_find_similar_by_embedding():
    from backend.infrastructure.persistence.in_memory import InMemoryProblemRepository

    repo = InMemoryProblemRepository()
    vec = [1.0, 0.0, 0.0]
    p = _make_problem()
    p.embedding = vec
    repo.add(p)

    results = repo.find_similar(embedding=vec, threshold=0.9)
    assert p.problem_id in [r.problem_id for r in results]


def test_inmemory_thread_repository_does_not_exist():
    import backend.infrastructure.persistence.in_memory as im

    assert not hasattr(im, "InMemoryThreadRepository")


def test_inmemory_comment_repository_does_not_exist():
    import backend.infrastructure.persistence.in_memory as im

    assert not hasattr(im, "InMemoryCommentRepository")


def test_inmemory_vote_repository_does_not_exist():
    import backend.infrastructure.persistence.in_memory as im

    assert not hasattr(im, "InMemoryVoteRepository")


# ---------------------------------------------------------------------------
# InMemorySolutionRepository tests
# ---------------------------------------------------------------------------


def test_solution_repo_delete_removes_solution():
    from backend.infrastructure.persistence.in_memory import InMemorySolutionRepository

    repo = InMemorySolutionRepository()
    s = _make_solution()
    repo.add(s)
    repo.delete(s.solution_id)
    assert repo.get(s.solution_id) is None


def test_solution_repo_find_unreviewed_returns_none_status():
    from backend.infrastructure.persistence.in_memory import InMemorySolutionRepository

    repo = InMemorySolutionRepository()
    s_pending = _make_solution()
    s_approved = _make_solution(problem_id=s_pending.problem_id)
    s_approved.review_status = "approved"

    repo.add(s_pending)
    repo.add(s_approved)

    results = repo.find_unreviewed(limit=10)
    ids = [r.solution_id for r in results]
    assert s_pending.solution_id in ids
    assert s_approved.solution_id not in ids


def test_solution_repo_find_unreviewed_includes_error_with_cutoff():
    from backend.infrastructure.persistence.in_memory import InMemorySolutionRepository

    repo = InMemorySolutionRepository()
    s_error = _make_solution()
    s_error.review_status = "error"
    repo.add(s_error)

    no_cutoff = repo.find_unreviewed(limit=10)
    assert s_error.solution_id not in [r.solution_id for r in no_cutoff]

    cutoff = datetime.now(tz=UTC) + timedelta(seconds=1)
    with_cutoff = repo.find_unreviewed(limit=10, retry_error_before=cutoff)
    assert s_error.solution_id in [r.solution_id for r in with_cutoff]


def test_solution_repo_list_by_problem_ranked_by_confidence():
    from backend.infrastructure.persistence.in_memory import InMemorySolutionRepository

    repo = InMemorySolutionRepository()
    pid = uuid4()
    s_low = _make_solution(problem_id=pid)
    s_low.confidence = 0.3
    s_low.review_status = "approved"

    s_high = _make_solution(problem_id=pid)
    s_high.confidence = 0.8
    s_high.review_status = "approved"

    # Matches SQL: all solutions returned regardless of review_status, non-superseded first
    s_unapproved = _make_solution(problem_id=pid)
    s_unapproved.confidence = 0.99
    s_unapproved.review_status = None

    # Superseded solution should appear after non-superseded even with high confidence
    s_superseded = _make_solution(problem_id=pid)
    s_superseded.confidence = 0.95
    s_superseded.canonical_id = s_high.solution_id  # marked as superseded

    repo.add(s_low)
    repo.add(s_high)
    repo.add(s_unapproved)
    repo.add(s_superseded)

    ranked = repo.list_by_problem_ranked(pid)
    # All solutions returned; non-superseded first (canonical_id is None), then by confidence
    non_superseded_ids = [r.solution_id for r in ranked if r.canonical_id is None]
    superseded_ids = [r.solution_id for r in ranked if r.canonical_id is not None]
    assert s_unapproved.solution_id in non_superseded_ids
    assert s_high.solution_id in non_superseded_ids
    assert s_superseded.solution_id in superseded_ids
    # Non-superseded entries appear before superseded entries in the list
    first_superseded_idx = next(
        i for i, r in enumerate(ranked) if r.canonical_id is not None
    )
    assert all(ranked[i].canonical_id is None for i in range(first_superseded_idx))


def test_solution_repo_find_superseded_returns_canonical_solutions():
    from backend.infrastructure.persistence.in_memory import InMemorySolutionRepository

    repo = InMemorySolutionRepository()
    pid = uuid4()
    canonical = _make_solution(problem_id=pid)
    superseded = _make_solution(problem_id=pid)
    superseded.canonical_id = canonical.solution_id

    repo.add(canonical)
    repo.add(superseded)

    superseded_list = repo.find_superseded(pid)
    ids = [s.solution_id for s in superseded_list]
    assert superseded.solution_id in ids
    assert canonical.solution_id not in ids


# ---------------------------------------------------------------------------
# InMemoryTokenTransactionRepository tests
# ---------------------------------------------------------------------------


def test_token_transaction_repo_clear_related_solution():
    from backend.domain.models import TokenTransaction
    from backend.infrastructure.persistence.in_memory import (
        InMemoryTokenTransactionRepository,
    )

    repo = InMemoryTokenTransactionRepository()
    sol_id = uuid4()
    tx = TokenTransaction(
        agent_id=uuid4(),
        amount=5,
        tx_type="outcome_reward",
        related_solution_id=sol_id,
        description="reward",
    )
    repo.add(tx)

    repo.clear_related_solution(sol_id)
    transactions = repo.list_by_agent(tx.agent_id)
    assert transactions[0].related_solution_id is None


def test_token_transaction_repo_has_no_clear_related_comment():
    from backend.infrastructure.persistence.in_memory import (
        InMemoryTokenTransactionRepository,
    )

    repo = InMemoryTokenTransactionRepository()
    assert not hasattr(repo, "clear_related_comment")
