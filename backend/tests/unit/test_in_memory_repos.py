"""Unit tests for in-memory repository implementations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from backend.domain.models import Problem, Solution
from backend.infrastructure.persistence import in_memory as in_memory_module
from backend.infrastructure.persistence.in_memory import (
    InMemoryProblemRepository,
    InMemorySolutionRepository,
)


def _make_problem(**kwargs):
    defaults = {
        "author_id": uuid4(),
        "description": "Test problem description that is long enough",
    }
    defaults.update(kwargs)
    return Problem(**defaults)


def _make_solution(problem_id=None, **kwargs):
    defaults = {
        "problem_id": problem_id or uuid4(),
        "author_id": uuid4(),
        "content": "Fix the issue by running the command",
    }
    defaults.update(kwargs)
    return Solution(**defaults)


# InMemoryProblemRepository tests


def test_given_problem_repo_when_adding_and_getting_then_same_problem_is_returned():
    repo = InMemoryProblemRepository()
    p = _make_problem()
    repo.add(p)
    assert repo.get(p.problem_id) == p


def test_given_problem_repo_when_deleting_problem_then_problem_is_removed():
    repo = InMemoryProblemRepository()
    p = _make_problem()
    repo.add(p)
    repo.delete(p.problem_id)
    assert repo.get(p.problem_id) is None


def test_given_problem_review_states_when_listing_unreviewed_then_only_pending_is_returned():
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


def test_given_problem_in_error_state_when_retry_cutoff_is_provided_then_problem_is_retried():
    repo = InMemoryProblemRepository()
    p_error = _make_problem()
    p_error.review_status = "error"

    repo.add(p_error)

    no_cutoff = repo.find_unreviewed(limit=10)
    assert p_error.problem_id not in [r.problem_id for r in no_cutoff]

    cutoff = datetime.now(tz=UTC) + timedelta(seconds=1)
    with_cutoff = repo.find_unreviewed(limit=10, retry_error_before=cutoff)
    assert p_error.problem_id in [r.problem_id for r in with_cutoff]


def test_given_problem_candidates_when_querying_research_candidates_then_low_confidence_approved_problem_is_included():
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


def test_given_problem_embedding_when_querying_similar_then_matching_embedding_problem_is_returned():
    repo = InMemoryProblemRepository()
    vec = [1.0, 0.0, 0.0]
    p = _make_problem()
    p.embedding = vec
    repo.add(p)

    results = repo.find_similar(embedding=vec, threshold=0.9)
    assert p.problem_id in [r.problem_id for r in results]


@pytest.mark.parametrize(
    "removed_repo_name",
    ["InMemoryThreadRepository", "InMemoryCommentRepository", "InMemoryVoteRepository"],
)
def test_given_removed_inmemory_repo_symbol_when_inspecting_module_then_symbol_is_absent(
    removed_repo_name: str,
):
    assert not hasattr(in_memory_module, removed_repo_name)


# InMemorySolutionRepository tests


def test_given_solution_repo_when_deleting_solution_then_solution_is_removed():
    repo = InMemorySolutionRepository()
    s = _make_solution()
    repo.add(s)
    repo.delete(s.solution_id)
    assert repo.get(s.solution_id) is None


def test_given_solution_review_states_when_listing_unreviewed_then_only_pending_is_returned():
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


def test_given_solution_in_error_state_when_retry_cutoff_is_provided_then_solution_is_retried():
    repo = InMemorySolutionRepository()
    s_error = _make_solution()
    s_error.review_status = "error"
    repo.add(s_error)

    no_cutoff = repo.find_unreviewed(limit=10)
    assert s_error.solution_id not in [r.solution_id for r in no_cutoff]

    cutoff = datetime.now(tz=UTC) + timedelta(seconds=1)
    with_cutoff = repo.find_unreviewed(limit=10, retry_error_before=cutoff)
    assert s_error.solution_id in [r.solution_id for r in with_cutoff]


def test_given_problem_solutions_when_listing_ranked_then_non_superseded_entries_come_first_and_by_confidence():
    repo = InMemorySolutionRepository()
    pid = uuid4()
    s_low = _make_solution(problem_id=pid)
    s_low.confidence = 0.3
    s_low.review_status = "approved"

    s_high = _make_solution(problem_id=pid)
    s_high.confidence = 0.8
    s_high.review_status = "approved"

    s_unapproved = _make_solution(problem_id=pid)
    s_unapproved.confidence = 0.99
    s_unapproved.review_status = None

    s_superseded = _make_solution(problem_id=pid)
    s_superseded.confidence = 0.95
    s_superseded.canonical_id = s_high.solution_id

    repo.add(s_low)
    repo.add(s_high)
    repo.add(s_unapproved)
    repo.add(s_superseded)

    ranked = repo.list_by_problem_ranked(pid)
    non_superseded_ids = [r.solution_id for r in ranked if r.canonical_id is None]
    superseded_ids = [r.solution_id for r in ranked if r.canonical_id is not None]
    assert s_unapproved.solution_id in non_superseded_ids
    assert s_high.solution_id in non_superseded_ids
    assert s_superseded.solution_id in superseded_ids
    first_superseded_idx = next(
        i for i, r in enumerate(ranked) if r.canonical_id is not None
    )
    assert all(ranked[i].canonical_id is None for i in range(first_superseded_idx))


def test_given_problem_with_canonical_and_superseded_solutions_when_listing_superseded_then_only_superseded_is_returned():
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


def test_given_removed_inmemory_token_transaction_repo_when_inspecting_module_then_symbol_is_absent():
    assert not hasattr(in_memory_module, "InMemoryTokenTransactionRepository")
