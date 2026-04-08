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

from backend.domain.models import Outcome, Problem, Solution
from backend.infrastructure.persistence.database import engine
from backend.infrastructure.persistence.sqlalchemy_repositories import (
    SQLAlchemyOutcomeRepository,
    SQLAlchemyProblemRepository,
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


# ---------------------------------------------------------------------------
# Fixtures — each test gets a rolled-back session to avoid pollution
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Helper: ensure a real agent row exists (satisfies FK constraints)
# ---------------------------------------------------------------------------


def _ensure_agent(sess: Session, agent_id: UUID) -> None:
    from backend.infrastructure.persistence.sqlalchemy_models import AgentORM

    existing = sess.get(AgentORM, str(agent_id))
    if existing is None:
        sess.add(
            AgentORM(
                agent_id=str(agent_id),
                api_key_hash=f"hash_{agent_id.hex}",
                model_type="test",
                reputation=0.0,
                token_balance=100,
                created_at=datetime.now(tz=UTC),
                last_active_at=datetime.now(tz=UTC),
            )
        )


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# ProblemRepository tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# SolutionRepository tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# OutcomeRepository tests
# ---------------------------------------------------------------------------


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
