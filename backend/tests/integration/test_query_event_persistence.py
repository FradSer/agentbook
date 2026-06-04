"""Integration: SQLAlchemyQueryEventRepository persistence + in-memory parity.

Requires: RUN_DOCKER_TESTS=1 and a running PostgreSQL with migrations applied.
Each test wraps in a transaction that is rolled back after the test.

Pins the recurrence-density instrument's DB path to the same dedup/rollup
semantics as ``InMemoryQueryEventRepository`` by replaying a shared event
fixture through both repos and asserting identical numbers — parity by shared
implementation (``backend.application._recurrence.compute_recurrence_rollup``),
not by coincidence. Also covers FK/cascade and windowed-count behaviour on a
real database.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from backend.domain.models import Problem, QueryEvent, utc_now
from backend.infrastructure.persistence.database import engine
from backend.infrastructure.persistence.sqlalchemy_models import (
    AgentORM,
    QueryEventORM,
)
from backend.infrastructure.persistence.sqlalchemy_repositories import (
    SQLAlchemyAgentRepository,
    SQLAlchemyProblemRepository,
    SQLAlchemyQueryEventRepository,
)

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        os.getenv("RUN_DOCKER_TESTS") != "1",
        reason="Set RUN_DOCKER_TESTS=1 to run integration tests",
    ),
]

AUTHOR_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture()
def session():
    """Provide a session that rolls back after each test."""
    with engine.connect() as conn:
        trans = conn.begin()
        sess = Session(bind=conn, join_transaction_mode="create_savepoint")
        _ensure_agent(sess, AUTHOR_ID)
        sess.flush()
        yield sess
        sess.close()
        trans.rollback()


@pytest.fixture()
def session_factory(session):
    @contextmanager
    def factory():
        yield session

    return factory


def _ensure_agent(sess: Session, agent_id: UUID) -> None:
    existing = sess.get(AgentORM, str(agent_id))
    if existing is None:
        sess.add(
            AgentORM(
                agent_id=str(agent_id),
                api_key_hash=f"hash_{agent_id.hex}",
                model_type="test",
                created_at=datetime.now(tz=UTC),
                last_active_at=datetime.now(tz=UTC),
            )
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
        top_match_problem_id=problem_id,
        top_match_quality=quality,
        has_help=has_help,
        is_self_hit=is_self_hit,
        is_seed_replay=is_seed_replay,
        created_at=created_at if created_at is not None else utc_now(),
    )


def _build_parity_fixture(problem_id: UUID, seed_author: UUID) -> list[QueryEvent]:
    """Shared event sequence replayed through both repos.

    Mixes strong/weak hits, a seed-replay (excluded from the denominator), a
    self-hit (excluded from the numerator), and a seed-contributor hit (excluded
    from organic recurrence) so the rollup exercises every branch.
    """
    organic_author = AUTHOR_ID
    return [
        _event(agent_id=organic_author, problem_id=problem_id, quality="strong"),
        _event(agent_id=organic_author, problem_id=problem_id, quality="exact"),
        _event(agent_id=seed_author, problem_id=problem_id, quality="strong"),
        _event(problem_id=problem_id, quality="weak", has_help=False),
        _event(problem_id=problem_id, quality="strong", has_help=False),
        _event(problem_id=problem_id, is_self_hit=True),
        _event(problem_id=problem_id, is_seed_replay=True),
    ]


# Parity — the contract this batch exists to guarantee


def test_db_rollup_matches_in_memory_on_shared_fixture(
    session_factory, session
) -> None:
    """recurrence_rollup matches the in-memory repo on the same fixture.

    Same numbers come out of both backends because both delegate to the one
    shared metric helper — the DB path cannot silently diverge.
    """
    from backend.infrastructure.persistence.in_memory import (
        InMemoryQueryEventRepository,
    )

    seed_author = uuid4()
    _ensure_agent(session, seed_author)
    problem = Problem(author_id=AUTHOR_ID, description="recurrence parity problem")
    SQLAlchemyProblemRepository(session_factory).add(problem)
    session.flush()

    fixture = _build_parity_fixture(problem.problem_id, seed_author)
    seed_ids = frozenset({seed_author})

    in_memory = InMemoryQueryEventRepository()
    for event in fixture:
        in_memory.add(event)

    db_repo = SQLAlchemyQueryEventRepository(session_factory)
    for event in fixture:
        db_repo.add(event)

    expected = in_memory.recurrence_rollup(seed_agent_ids=seed_ids)
    actual = db_repo.recurrence_rollup(seed_agent_ids=seed_ids)

    assert actual["recurrence_density"] == expected["recurrence_density"]
    assert actual["organic_recurrence"] == expected["organic_recurrence"]
    assert actual["total_independent_queries"] == expected["total_independent_queries"]
    assert actual["per_problem"] == expected["per_problem"]


def test_add_with_dedup_excludes_seed_replay_and_self_hits(
    session_factory, session
) -> None:
    """Seed-replay and self-hit events are dropped, never persisted."""
    repo = SQLAlchemyQueryEventRepository(session_factory)
    agents = SQLAlchemyAgentRepository(session_factory)
    problem = Problem(author_id=AUTHOR_ID, description="dedup problem")
    SQLAlchemyProblemRepository(session_factory).add(problem)
    session.flush()

    assert (
        repo.add_with_dedup(
            _event(problem_id=problem.problem_id, is_seed_replay=True), agents
        )
        is False
    )
    assert (
        repo.add_with_dedup(
            _event(problem_id=problem.problem_id, is_self_hit=True), agents
        )
        is False
    )
    assert repo.list_all() == []


def test_add_with_dedup_collapses_same_identity_within_window(
    session_factory, session
) -> None:
    """Same anonymous identity on the same problem inside the window counts once."""
    repo = SQLAlchemyQueryEventRepository(session_factory)
    agents = SQLAlchemyAgentRepository(session_factory)
    problem = Problem(author_id=AUTHOR_ID, description="window problem")
    SQLAlchemyProblemRepository(session_factory).add(problem)
    session.flush()

    base = utc_now()
    first = _event(
        ip_hash="ip-a",
        fingerprint_hash="fp-a",
        problem_id=problem.problem_id,
        created_at=base,
    )
    second = _event(
        ip_hash="ip-a",
        fingerprint_hash="fp-a",
        problem_id=problem.problem_id,
        created_at=base + timedelta(seconds=30),
    )

    assert repo.add_with_dedup(first, agents, dedup_window_seconds=600) is True
    assert repo.add_with_dedup(second, agents, dedup_window_seconds=600) is False
    assert len(repo.list_all()) == 1


def test_persists_with_fk_intact_and_cascades_on_problem_delete(
    session_factory, session
) -> None:
    """Events persist with a real problem FK; deleting the problem cascades."""
    repo = SQLAlchemyQueryEventRepository(session_factory)
    problem_repo = SQLAlchemyProblemRepository(session_factory)
    problem = Problem(author_id=AUTHOR_ID, description="cascade problem")
    problem_repo.add(problem)
    session.flush()

    repo.add(_event(agent_id=AUTHOR_ID, problem_id=problem.problem_id))
    rows = repo.list_all()
    assert len(rows) == 1
    assert rows[0].top_match_problem_id == problem.problem_id
    assert rows[0].agent_id == AUTHOR_ID

    problem_repo.delete(problem.problem_id)
    session.flush()
    remaining = (
        session.query(QueryEventORM)
        .filter(QueryEventORM.problem_id == str(problem.problem_id))
        .count()
    )
    assert remaining == 0


def test_windowed_counts_from_db(session_factory, session) -> None:
    """list_all(since=...) and query_count_for_problem return DB-backed windows."""
    repo = SQLAlchemyQueryEventRepository(session_factory)
    problem_repo = SQLAlchemyProblemRepository(session_factory)
    problem = Problem(author_id=AUTHOR_ID, description="windowed problem")
    problem_repo.add(problem)
    session.flush()

    now = utc_now()
    old = now - timedelta(days=2)
    repo.add(_event(problem_id=problem.problem_id, created_at=now))
    repo.add(_event(problem_id=problem.problem_id, created_at=now))
    repo.add(_event(problem_id=problem.problem_id, created_at=old))
    repo.add(_event(problem_id=problem.problem_id, is_seed_replay=True, created_at=now))
    repo.add(_event(problem_id=problem.problem_id, is_self_hit=True, created_at=now))

    since = now - timedelta(days=1)
    assert len(repo.list_all(since=since)) == 4
    # Seed-replay and self-hit are excluded; only 2 of the windowed rows count.
    assert repo.query_count_for_problem(problem.problem_id, since=since) == 2
