"""Integration tests for SQLAlchemy repositories.

Requires: RUN_DOCKER_TESTS=1 and a running PostgreSQL with migrations applied.
Each test wraps in a transaction that is rolled back after the test.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from backend.domain.models import Outcome, Problem, ResearchCycle, Solution
from backend.infrastructure.persistence.database import engine
from backend.infrastructure.persistence.sqlalchemy_repositories import (
    SQLAlchemyOutcomeRepository,
    SQLAlchemyProblemRepository,
    SQLAlchemyResearchCycleRepository,
    SQLAlchemySolutionRepository,
)

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        os.getenv("RUN_DOCKER_TESTS") != "1",
        reason="Set RUN_DOCKER_TESTS=1 to run integration tests",
    ),
]

AUTHOR_ID = UUID("00000000-0000-0000-0000-000000000001")


# Fixtures — each test gets a rolled-back session to avoid pollution


@pytest.fixture()
def session():
    """Provide a session that rolls back after each test."""
    with engine.connect() as conn:
        trans = conn.begin()
        sess = Session(bind=conn)
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


# Helper: ensure a real agent row exists (satisfies FK constraints)


def _ensure_agent(sess: Session, agent_id: UUID) -> None:
    from backend.infrastructure.persistence.sqlalchemy_models import AgentORM

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


# Helper factories


def _make_problem(**kwargs) -> Problem:
    return Problem(author_id=AUTHOR_ID, **{"description": "test problem", **kwargs})


def _make_solution(problem_id: UUID, **kwargs) -> Solution:
    return Solution(
        problem_id=problem_id,
        author_id=AUTHOR_ID,
        **{"content": "test solution", **kwargs},
    )


def _make_outcome(
    session: Session, solution_id: UUID, reporter_id: UUID | None = None, **kwargs
) -> Outcome:
    rid = reporter_id or uuid4()
    _ensure_agent(session, rid)
    session.flush()
    return Outcome(
        solution_id=solution_id,
        reporter_id=rid,
        success=True,
        **kwargs,
    )


# ProblemRepository tests


def test_problem_add_and_get(session_factory, session) -> None:
    """add(problem) persists; get(problem_id) retrieves it."""
    repo = SQLAlchemyProblemRepository(session_factory)
    p = _make_problem()
    repo.add(p)
    fetched = repo.get(p.problem_id)
    assert fetched is not None
    assert fetched.problem_id == p.problem_id
    assert fetched.description == p.description


def test_problem_find_by_error_signature(session_factory) -> None:
    """find_by_error_signature returns exact match."""
    repo = SQLAlchemyProblemRepository(session_factory)
    sig = f"ImportError: {uuid4().hex}"
    p = _make_problem(error_signature=sig)
    repo.add(p)
    found = repo.find_by_error_signature(sig)
    assert found is not None
    assert found.problem_id == p.problem_id


def test_problem_find_by_error_signature_miss(session_factory) -> None:
    """find_by_error_signature returns None for unknown signature."""
    repo = SQLAlchemyProblemRepository(session_factory)
    result = repo.find_by_error_signature("NoSuchError: xyz")
    assert result is None


def test_problem_find_similar_returns_results(session_factory) -> None:
    """find_similar returns problems whose embeddings are close."""
    repo = SQLAlchemyProblemRepository(session_factory)
    embedding = [0.1] * 1536
    p = _make_problem(embedding=embedding)
    repo.add(p)
    results = repo.find_similar(embedding, threshold=0.5)
    ids = [r.problem_id for r in results]
    assert p.problem_id in ids


def test_problem_update(session_factory) -> None:
    """update persists changes to an existing problem."""
    repo = SQLAlchemyProblemRepository(session_factory)
    p = _make_problem()
    repo.add(p)
    p.best_confidence = 0.9
    repo.update(p)
    fetched = repo.get(p.problem_id)
    assert fetched is not None
    assert fetched.best_confidence == pytest.approx(0.9)


def test_problem_list_all(session_factory) -> None:
    """list_all returns all added problems."""
    repo = SQLAlchemyProblemRepository(session_factory)
    p1, p2 = _make_problem(), _make_problem()
    repo.add(p1)
    repo.add(p2)
    all_problems = repo.list_all()
    ids = {p.problem_id for p in all_problems}
    assert p1.problem_id in ids
    assert p2.problem_id in ids


# SolutionRepository tests


def test_solution_add_and_get(session_factory) -> None:
    """add(solution) persists; get(solution_id) retrieves it."""
    prob_repo = SQLAlchemyProblemRepository(session_factory)
    sol_repo = SQLAlchemySolutionRepository(session_factory)
    p = _make_problem()
    prob_repo.add(p)
    s = _make_solution(p.problem_id)
    sol_repo.add(s)
    fetched = sol_repo.get(s.solution_id)
    assert fetched is not None
    assert fetched.solution_id == s.solution_id


def test_solution_list_by_problem_sorted_by_confidence(session_factory) -> None:
    """list_by_problem returns solutions sorted by confidence descending."""
    prob_repo = SQLAlchemyProblemRepository(session_factory)
    sol_repo = SQLAlchemySolutionRepository(session_factory)
    p = _make_problem()
    prob_repo.add(p)
    s1 = _make_solution(p.problem_id, confidence=0.8)
    s2 = _make_solution(p.problem_id, confidence=0.3)
    sol_repo.add(s1)
    sol_repo.add(s2)
    solutions = sol_repo.list_by_problem(p.problem_id)
    assert len(solutions) == 2
    assert solutions[0].confidence >= solutions[1].confidence


def test_solution_update(session_factory) -> None:
    """update persists confidence change."""
    prob_repo = SQLAlchemyProblemRepository(session_factory)
    sol_repo = SQLAlchemySolutionRepository(session_factory)
    p = _make_problem()
    prob_repo.add(p)
    s = _make_solution(p.problem_id)
    sol_repo.add(s)
    s.confidence = 0.95
    sol_repo.update(s)
    fetched = sol_repo.get(s.solution_id)
    assert fetched is not None
    assert fetched.confidence == pytest.approx(0.95)


# OutcomeRepository tests


def test_outcome_add_and_list_by_solution(session_factory, session) -> None:
    """add persists outcome; list_by_solution returns it."""
    prob_repo = SQLAlchemyProblemRepository(session_factory)
    sol_repo = SQLAlchemySolutionRepository(session_factory)
    out_repo = SQLAlchemyOutcomeRepository(session_factory)
    p = _make_problem()
    prob_repo.add(p)
    s = _make_solution(p.problem_id)
    sol_repo.add(s)
    o = _make_outcome(session, s.solution_id)
    out_repo.add(o)
    outcomes = out_repo.list_by_solution(s.solution_id)
    assert any(oc.outcome_id == o.outcome_id for oc in outcomes)


def test_outcome_count_by_reporter(session_factory, session) -> None:
    """count_by_reporter counts outcomes within the time window."""
    prob_repo = SQLAlchemyProblemRepository(session_factory)
    sol_repo = SQLAlchemySolutionRepository(session_factory)
    out_repo = SQLAlchemyOutcomeRepository(session_factory)
    p = _make_problem()
    prob_repo.add(p)
    s = _make_solution(p.problem_id)
    sol_repo.add(s)
    reporter = uuid4()
    o1 = _make_outcome(session, s.solution_id, reporter_id=reporter)
    o2 = _make_outcome(session, s.solution_id, reporter_id=reporter)
    out_repo.add(o1)
    out_repo.add(o2)
    since = datetime.now(tz=UTC) - timedelta(hours=1)
    count = out_repo.count_by_reporter(reporter, since=since)
    assert count == 2


def test_outcome_list_by_reporter(session_factory, session) -> None:
    """list_by_reporter returns only outcomes from the given reporter."""
    prob_repo = SQLAlchemyProblemRepository(session_factory)
    sol_repo = SQLAlchemySolutionRepository(session_factory)
    out_repo = SQLAlchemyOutcomeRepository(session_factory)
    p = _make_problem()
    prob_repo.add(p)
    s = _make_solution(p.problem_id)
    sol_repo.add(s)
    reporter = uuid4()
    matching = _make_outcome(session, s.solution_id, reporter_id=reporter)
    out_repo.add(matching)
    out_repo.add(_make_outcome(session, s.solution_id, reporter_id=uuid4()))

    listed = out_repo.list_by_reporter(reporter)
    assert [o.outcome_id for o in listed] == [matching.outcome_id]


# Live-research banner: list_being_researched + get_latest_cycle_at


def _make_research_cycle(problem_id: UUID, **kwargs) -> ResearchCycle:
    return ResearchCycle(
        problem_id=problem_id,
        researcher_id=AUTHOR_ID,
        status=kwargs.pop("status", "no_improvement"),
        **kwargs,
    )


def test_given_mixed_research_started_at_when_listing_being_researched_then_only_fresh_rows_are_returned(
    session_factory,
) -> None:
    """list_being_researched honours the freshness window (359s in, 361s out, NULL out)."""
    repo = SQLAlchemyProblemRepository(session_factory)
    now = datetime.now(tz=UTC)

    fresh = _make_problem()
    fresh.research_started_at = now - timedelta(seconds=359)
    repo.add(fresh)

    stale = _make_problem()
    stale.research_started_at = now - timedelta(seconds=361)
    repo.add(stale)

    inactive = _make_problem()
    inactive.research_started_at = None
    repo.add(inactive)

    results = repo.list_being_researched(timeout_seconds=360)
    ids = [r.problem_id for r in results]
    assert fresh.problem_id in ids
    assert stale.problem_id not in ids
    assert inactive.problem_id not in ids


def test_given_two_fresh_problems_when_listing_being_researched_then_results_are_ordered_desc(
    session_factory,
) -> None:
    """list_being_researched orders by research_started_at descending."""
    repo = SQLAlchemyProblemRepository(session_factory)
    now = datetime.now(tz=UTC)

    older = _make_problem()
    older.research_started_at = now - timedelta(seconds=200)
    repo.add(older)

    newer = _make_problem()
    newer.research_started_at = now - timedelta(seconds=10)
    repo.add(newer)

    results = repo.list_being_researched(timeout_seconds=360)
    ids = [r.problem_id for r in results]
    assert ids.index(newer.problem_id) < ids.index(older.problem_id)


def test_given_no_active_research_when_listing_being_researched_then_empty_list_is_returned(
    session_factory,
) -> None:
    """Returns empty when every problem has research_started_at IS NULL."""
    repo = SQLAlchemyProblemRepository(session_factory)
    p1 = _make_problem()
    p2 = _make_problem()
    repo.add(p1)
    repo.add(p2)

    results = repo.list_being_researched(timeout_seconds=360)
    ids = {r.problem_id for r in results}
    assert p1.problem_id not in ids
    assert p2.problem_id not in ids


def test_given_empty_research_cycles_when_getting_latest_cycle_at_then_none_is_returned(
    session_factory,
) -> None:
    """get_latest_cycle_at returns None when research_cycles is empty."""
    repo = SQLAlchemyResearchCycleRepository(session_factory)
    assert repo.get_latest_cycle_at() is None


def test_given_three_cycles_when_getting_latest_cycle_at_then_max_created_at_is_returned(
    session_factory,
) -> None:
    """get_latest_cycle_at returns MAX(created_at) across stored cycles."""
    prob_repo = SQLAlchemyProblemRepository(session_factory)
    cycle_repo = SQLAlchemyResearchCycleRepository(session_factory)

    p = _make_problem()
    prob_repo.add(p)

    now = datetime.now(tz=UTC)
    earliest = now - timedelta(minutes=10)
    middle = now - timedelta(minutes=5)
    latest = now - timedelta(minutes=1)

    cycle_repo.add(_make_research_cycle(p.problem_id, created_at=earliest))
    cycle_repo.add(_make_research_cycle(p.problem_id, created_at=middle))
    cycle_repo.add(_make_research_cycle(p.problem_id, created_at=latest))

    result = repo_latest = cycle_repo.get_latest_cycle_at()
    assert result is not None
    # tolerate microsecond rounding by comparing within 1 second
    assert abs((repo_latest - latest).total_seconds()) < 1.0
