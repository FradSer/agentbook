"""Unit tests for in-memory repository implementations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from backend.domain.models import Outcome, Problem, ResearchCycle, Solution
from backend.infrastructure.persistence import in_memory as in_memory_module
from backend.infrastructure.persistence.in_memory import (
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)


def _make_problem(**kwargs):
    defaults = {
        "author_id": uuid4(),
        "description": "Test problem description that is long enough",
    }
    defaults.update(kwargs)
    return Problem(**defaults)


def _make_research_cycle(created_at: datetime) -> ResearchCycle:
    return ResearchCycle(
        problem_id=uuid4(),
        researcher_id=uuid4(),
        status="no_improvement",
        created_at=created_at,
    )


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


def test_given_problem_repo_when_get_by_ids_then_resolves_known_and_skips_missing():
    repo = InMemoryProblemRepository()
    p1 = _make_problem()
    p2 = _make_problem()
    repo.add(p1)
    repo.add(p2)
    missing = uuid4()

    result = repo.get_by_ids([p1.problem_id, missing, p2.problem_id])

    assert result == {p1.problem_id: p1, p2.problem_id: p2}
    assert repo.get_by_ids([]) == {}


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


# ---------------------------------------------------------------------------
# Tests consolidated from test_repositories.py
# ---------------------------------------------------------------------------


def test_given_problem_repo_when_listing_all_then_all_added_problems_are_returned():
    repo = InMemoryProblemRepository()
    p1 = _make_problem(description="first")
    p2 = _make_problem(description="second")

    repo.add(p1)
    repo.add(p2)
    results = repo.list_all()

    assert len(results) == 2
    ids = {r.problem_id for r in results}
    assert p1.problem_id in ids
    assert p2.problem_id in ids


def test_given_problem_with_error_signature_when_finding_then_matching_problem_is_returned():
    repo = InMemoryProblemRepository()
    problem = _make_problem(error_signature="TypeError: foo is not a function")
    repo.add(problem)

    assert repo.find_by_error_signature("TypeError: foo is not a function") is problem


def test_given_problem_repo_when_finding_by_nonexistent_error_signature_then_none_is_returned():
    repo = InMemoryProblemRepository()
    repo.add(_make_problem(error_signature="SomeError"))

    assert repo.find_by_error_signature("nonexistent") is None


def test_given_orthogonal_embeddings_when_finding_similar_then_problem_is_excluded():
    repo = InMemoryProblemRepository()
    p = _make_problem()
    p.embedding = [1.0, 0.0, 0.0]
    repo.add(p)

    results = repo.find_similar(embedding=[0.0, 1.0, 0.0], threshold=0.9)
    assert p.problem_id not in [r.problem_id for r in results]


def test_given_problem_repo_when_updating_then_changes_are_persisted():
    repo = InMemoryProblemRepository()
    problem = _make_problem()
    repo.add(problem)

    object.__setattr__(problem, "description", "updated description")
    repo.update(problem)

    assert repo.get(problem.problem_id).description == "updated description"


def test_given_solution_repo_when_updating_then_changes_are_persisted():
    repo = InMemorySolutionRepository()
    solution = _make_solution()
    repo.add(solution)

    object.__setattr__(solution, "confidence", 0.95)
    repo.update(solution)

    assert repo.get(solution.solution_id).confidence == 0.95


# InMemoryOutcomeRepository tests


def _make_outcome(solution_id, reporter_id=None, **kwargs):
    return Outcome(
        solution_id=solution_id,
        reporter_id=reporter_id or uuid4(),
        success=True,
        **kwargs,
    )


def test_given_outcome_repo_when_adding_then_list_by_solution_returns_it():
    repo = InMemoryOutcomeRepository()
    solution_id = uuid4()
    outcome = _make_outcome(solution_id)
    repo.add(outcome)

    assert outcome in repo.list_by_solution(solution_id)


def test_given_outcome_repo_when_listing_unknown_solution_then_empty_list_is_returned():
    repo = InMemoryOutcomeRepository()
    repo.add(_make_outcome(uuid4()))

    assert repo.list_by_solution(uuid4()) == []


def test_given_outcome_repo_when_counting_by_reporter_then_recent_outcomes_are_counted():
    repo = InMemoryOutcomeRepository()
    reporter_id = uuid4()
    since = datetime.now(tz=UTC) - timedelta(hours=1)
    repo.add(_make_outcome(uuid4(), reporter_id=reporter_id))

    assert repo.count_by_reporter(reporter_id, since=since) == 1


def test_given_outcome_repo_when_counting_with_future_since_then_zero_is_returned():
    repo = InMemoryOutcomeRepository()
    reporter_id = uuid4()
    repo.add(_make_outcome(uuid4(), reporter_id=reporter_id))

    future = datetime.now(tz=UTC) + timedelta(hours=1)
    assert repo.count_by_reporter(reporter_id, since=future) == 0


def test_given_outcome_repo_when_listing_by_reporter_then_only_matching_outcomes_are_returned():
    repo = InMemoryOutcomeRepository()
    reporter_id = uuid4()
    other_reporter = uuid4()
    matching = _make_outcome(uuid4(), reporter_id=reporter_id)
    repo.add(matching)
    repo.add(_make_outcome(uuid4(), reporter_id=other_reporter))

    assert repo.list_by_reporter(reporter_id) == [matching]


# ---------------------------------------------------------------------------
# Live-research banner: list_being_researched + get_latest_cycle_at
# ---------------------------------------------------------------------------


def test_given_problems_with_mixed_research_started_at_when_listing_being_researched_then_only_fresh_rows_are_returned():
    repo = InMemoryProblemRepository()
    now = datetime.now(tz=UTC)

    fresh = _make_problem(description="A fresh problem still being researched")
    object.__setattr__(fresh, "research_started_at", now - timedelta(seconds=359))

    stale = _make_problem(description="B stale problem past the freshness window")
    object.__setattr__(stale, "research_started_at", now - timedelta(seconds=361))

    inactive = _make_problem(description="C inactive problem with no research")
    object.__setattr__(inactive, "research_started_at", None)

    repo.add(fresh)
    repo.add(stale)
    repo.add(inactive)

    results = repo.list_being_researched(timeout_seconds=360)
    ids = [r.problem_id for r in results]
    assert fresh.problem_id in ids
    assert stale.problem_id not in ids
    assert inactive.problem_id not in ids


def test_given_two_fresh_problems_when_listing_being_researched_then_results_are_ordered_by_research_started_at_desc():
    repo = InMemoryProblemRepository()
    now = datetime.now(tz=UTC)

    older = _make_problem(description="older fresh research")
    object.__setattr__(older, "research_started_at", now - timedelta(seconds=200))

    newer = _make_problem(description="newer fresh research")
    object.__setattr__(newer, "research_started_at", now - timedelta(seconds=10))

    repo.add(older)
    repo.add(newer)

    results = repo.list_being_researched(timeout_seconds=360)
    ids = [r.problem_id for r in results]
    assert ids == [newer.problem_id, older.problem_id]


def test_given_no_active_research_when_listing_being_researched_then_empty_list_is_returned():
    repo = InMemoryProblemRepository()
    p1 = _make_problem(description="never researched 1")
    p2 = _make_problem(description="never researched 2")
    repo.add(p1)
    repo.add(p2)

    assert repo.list_being_researched(timeout_seconds=360) == []


def test_given_empty_research_cycles_when_getting_latest_cycle_at_then_none_is_returned():
    repo = InMemoryResearchCycleRepository()
    assert repo.get_latest_cycle_at() is None


def test_given_three_cycles_when_getting_latest_cycle_at_then_max_created_at_is_returned():
    repo = InMemoryResearchCycleRepository()
    now = datetime.now(tz=UTC)
    earliest = now - timedelta(minutes=10)
    middle = now - timedelta(minutes=5)
    latest = now - timedelta(minutes=1)

    repo.add(_make_research_cycle(created_at=earliest))
    repo.add(_make_research_cycle(created_at=middle))
    repo.add(_make_research_cycle(created_at=latest))

    assert repo.get_latest_cycle_at() == latest
