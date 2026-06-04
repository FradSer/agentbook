"""Unit contract for the recurrence-density instrument's in-memory repo.

Pins the dedup rules (seed-replay / self-hit / same-identity-cluster) and the
RD / organic-recurrence rollup math. Task 005 (SQLAlchemy) must satisfy the
same behavior via the shared metric helper.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from backend.domain.models import QueryEvent, utc_now
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryQueryEventRepository,
)


def _event(
    *,
    agent_id=None,
    ip_hash=None,
    fingerprint_hash=None,
    problem_id=None,
    quality="strong",
    has_help=True,
    is_self_hit=False,
    is_seed_replay=False,
    created_at=None,
) -> QueryEvent:
    return QueryEvent(
        query_text="how do i fix the thing",
        agent_id=agent_id,
        ip_hash=ip_hash,
        fingerprint_hash=fingerprint_hash,
        top_match_problem_id=problem_id if problem_id is not None else uuid4(),
        top_match_quality=quality,
        has_help=has_help,
        is_self_hit=is_self_hit,
        is_seed_replay=is_seed_replay,
        created_at=created_at if created_at is not None else utc_now(),
    )


def test_seed_replay_dropped_and_not_recorded():
    repo = InMemoryQueryEventRepository()
    agents = InMemoryAgentRepository()

    recorded = repo.add_with_dedup(
        _event(is_seed_replay=True),
        agents,
        exclude_seed_replay=True,
    )

    assert recorded is False
    assert repo.list_all() == []


def test_self_hit_dropped_when_excluded():
    repo = InMemoryQueryEventRepository()
    agents = InMemoryAgentRepository()

    recorded = repo.add_with_dedup(
        _event(is_self_hit=True),
        agents,
        exclude_self_hits=True,
    )

    assert recorded is False
    assert repo.list_all() == []


def test_same_identity_cluster_replay_within_window_counts_once():
    repo = InMemoryQueryEventRepository()
    agents = InMemoryAgentRepository()

    problem_id = uuid4()
    base = utc_now()
    # Anonymous caller — same ip_hash/fingerprint_hash within the window
    # is the same identity cluster and must collapse to one independent query.
    first = _event(
        ip_hash="ip-a",
        fingerprint_hash="fp-a",
        problem_id=problem_id,
        created_at=base,
    )
    second = _event(
        ip_hash="ip-a",
        fingerprint_hash="fp-a",
        problem_id=problem_id,
        created_at=base + timedelta(seconds=30),
    )

    assert repo.add_with_dedup(first, agents, dedup_window_seconds=600) is True
    assert repo.add_with_dedup(second, agents, dedup_window_seconds=600) is False
    assert len(repo.list_all()) == 1


def test_recurrence_density_is_strong_with_help_nonself_over_independent():
    repo = InMemoryQueryEventRepository()

    # 3 strong-with-help, non-self hits + 7 other independent queries = 10
    # independent queries. RD = 3 / 10 = 0.30.
    for _ in range(3):
        repo.add(_event(quality="strong", has_help=True, is_self_hit=False))
    for _ in range(4):
        repo.add(_event(quality="weak", has_help=False, is_self_hit=False))
    for _ in range(3):
        # strong but no reliance target → not counted in the numerator
        repo.add(_event(quality="strong", has_help=False, is_self_hit=False))

    rollup = repo.recurrence_rollup()

    assert rollup["total_independent_queries"] == 10
    assert rollup["recurrence_density"] == 0.30


def test_organic_recurrence_excludes_seed_contributors():
    repo = InMemoryQueryEventRepository()

    organic_author = uuid4()
    seed_author = uuid4()

    # 4 strong-with-help hits total: 2 match a non-seed contributor (organic),
    # 2 match a seed contributor. organic_recurrence = 2 / 4 = 0.50.
    for _ in range(2):
        repo.add(_event(agent_id=organic_author, quality="strong", has_help=True))
    for _ in range(2):
        repo.add(_event(agent_id=seed_author, quality="strong", has_help=True))

    rollup = repo.recurrence_rollup(seed_agent_ids=frozenset({seed_author}))

    assert rollup["organic_recurrence"] == 0.50


def test_empty_and_all_seed_logs_yield_zero_rollup():
    empty_repo = InMemoryQueryEventRepository()
    empty = empty_repo.recurrence_rollup()
    assert empty["recurrence_density"] == 0.0
    assert empty["organic_recurrence"] == 0.0
    assert empty["total_independent_queries"] == 0
    assert empty["per_problem"] == []

    seed_repo = InMemoryQueryEventRepository()
    # Only seed-replay events present → all excluded, no division by zero.
    for _ in range(5):
        seed_repo.add(_event(is_seed_replay=True))
    seeded = seed_repo.recurrence_rollup()
    assert seeded["recurrence_density"] == 0.0
    assert seeded["organic_recurrence"] == 0.0
    assert seeded["total_independent_queries"] == 0


def test_query_count_for_problem_counts_only_non_seed_non_self():
    repo = InMemoryQueryEventRepository()
    problem_id = uuid4()

    repo.add(_event(problem_id=problem_id))
    repo.add(_event(problem_id=problem_id))
    repo.add(_event(problem_id=problem_id, is_seed_replay=True))
    repo.add(_event(problem_id=problem_id, is_self_hit=True))
    repo.add(_event(problem_id=uuid4()))  # different problem

    assert repo.query_count_for_problem(problem_id) == 2
