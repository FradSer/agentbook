"""Integration tests for the use-side dashboard against real PostgreSQL.

These tests exercise the SQLAlchemy implementations of the new repo methods
(``OutcomeRepository.aggregate_usage_metrics`` and
``OutcomeRepository.outcome_counts_by_solution_ids``) plus the end-to-end
``AgentbookService.get_usage_dashboard`` path. Unit tests cover the in-memory
implementations; this file is the smoke pass that verifies the SQL itself
(conditional aggregates, ``COUNT(DISTINCT)``, ``GROUP BY`` over a
problems/solutions/outcomes join) returns the same shape and values.

Requires: ``RUN_DOCKER_TESTS=1`` and a running PostgreSQL with migrations
applied. Each test wraps in a transaction that is rolled back after the test
so cross-test isolation matches the rest of ``test_sqlalchemy_repos.py``.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from backend.application.service import AgentbookService
from backend.domain.models import Outcome, Problem, Solution
from backend.infrastructure.embeddings.fallback import FallbackEmbeddingProvider
from backend.infrastructure.persistence.database import engine
from backend.infrastructure.persistence.sqlalchemy_models import AgentORM
from backend.infrastructure.persistence.sqlalchemy_repositories import (
    SQLAlchemyAgentRepository,
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


@pytest.fixture()
def service(session_factory) -> AgentbookService:
    """Wire all SQLAlchemy repos behind a real AgentbookService."""
    return AgentbookService(
        agents=SQLAlchemyAgentRepository(session_factory),
        embedding_provider=FallbackEmbeddingProvider(),
        problems=SQLAlchemyProblemRepository(session_factory),
        solutions=SQLAlchemySolutionRepository(session_factory),
        outcomes=SQLAlchemyOutcomeRepository(session_factory),
        research_cycles=SQLAlchemyResearchCycleRepository(session_factory),
    )


def _ensure_agent(sess: Session, agent_id: UUID) -> None:
    existing = sess.get(AgentORM, str(agent_id))
    if existing is None:
        sess.add(
            AgentORM(
                agent_id=str(agent_id),
                api_key_hash=f"hash_{agent_id.hex}",
                model_type="test",
                reputation=0.0,
                created_at=datetime.now(tz=UTC),
                last_active_at=datetime.now(tz=UTC),
            )
        )


def _seed_problem(
    service: AgentbookService,
    *,
    description: str = "smoke-test problem with sufficient description length.",
) -> Problem:
    problem = Problem(
        author_id=AUTHOR_ID,
        description=description,
        review_status="approved",
    )
    service._problems.add(problem)
    return problem


def _seed_solution(service: AgentbookService, problem_id: UUID) -> Solution:
    solution = Solution(
        problem_id=problem_id,
        author_id=AUTHOR_ID,
        content="smoke-test solution content with enough characters.",
        review_status="approved",
    )
    service._solutions.add(solution)
    return solution


def _seed_outcome(
    service: AgentbookService,
    session: Session,
    *,
    solution_id: UUID,
    reporter_id: UUID,
    created_at: datetime,
    success: bool = True,
    kind: str = "observed",
) -> None:
    """Insert an outcome with a controlled ``created_at``.

    ``service.report_outcome`` would stamp ``utc_now()``; we want windowed
    fixtures, so we go through the repo's ``add`` directly.
    """
    _ensure_agent(session, reporter_id)
    session.flush()
    service._outcomes.add(
        Outcome(
            solution_id=solution_id,
            reporter_id=reporter_id,
            success=success,
            kind=kind,
            created_at=created_at,
        )
    )


# ---------------------------------------------------------------------------
# OutcomeRepository.aggregate_usage_metrics
# ---------------------------------------------------------------------------


def test_aggregate_usage_metrics_empty_table_returns_zeros(service) -> None:
    now = datetime.now(tz=UTC)
    metrics = service._outcomes.aggregate_usage_metrics(now)
    assert metrics == {
        "outcomes_total": 0,
        "outcomes_last_7d": 0,
        "outcomes_last_30d": 0,
        "verified_total": 0,
        "observed_total": 0,
        "unique_reporters_total": 0,
        "unique_reporters_7d": 0,
        "unique_reporters_30d": 0,
    }


def test_aggregate_usage_metrics_windows_split_correctly(service, session) -> None:
    """COUNT FILTER + COUNT DISTINCT FILTER per window split must match
    the in-memory semantics: rows at 1d/8d/35d ago bucket as 1/2/3 in the
    7d/30d/total counts respectively."""
    now = datetime.now(tz=UTC)
    problem = _seed_problem(service)
    solution = _seed_solution(service, problem.problem_id)
    reporter = uuid4()

    _seed_outcome(
        service,
        session,
        solution_id=solution.solution_id,
        reporter_id=reporter,
        created_at=now - timedelta(days=1),
    )
    _seed_outcome(
        service,
        session,
        solution_id=solution.solution_id,
        reporter_id=reporter,
        created_at=now - timedelta(days=8),
    )
    _seed_outcome(
        service,
        session,
        solution_id=solution.solution_id,
        reporter_id=reporter,
        created_at=now - timedelta(days=35),
    )

    metrics = service._outcomes.aggregate_usage_metrics(now)
    assert metrics["outcomes_total"] == 3
    assert metrics["outcomes_last_7d"] == 1
    assert metrics["outcomes_last_30d"] == 2


def test_aggregate_usage_metrics_kind_split(service, session) -> None:
    now = datetime.now(tz=UTC)
    problem = _seed_problem(service)
    solution = _seed_solution(service, problem.problem_id)
    reporter = uuid4()

    for _ in range(2):
        _seed_outcome(
            service,
            session,
            solution_id=solution.solution_id,
            reporter_id=reporter,
            created_at=now - timedelta(hours=1),
            kind="verified",
        )
    for _ in range(3):
        _seed_outcome(
            service,
            session,
            solution_id=solution.solution_id,
            reporter_id=reporter,
            created_at=now - timedelta(hours=1),
            kind="observed",
        )

    metrics = service._outcomes.aggregate_usage_metrics(now)
    assert metrics["verified_total"] == 2
    assert metrics["observed_total"] == 3
    assert metrics["outcomes_total"] == 5


def test_aggregate_usage_metrics_unique_reporters_per_window(service, session) -> None:
    now = datetime.now(tz=UTC)
    problem = _seed_problem(service)
    solution = _seed_solution(service, problem.problem_id)

    # 3 distinct reporters in last 7 days
    for _ in range(3):
        _seed_outcome(
            service,
            session,
            solution_id=solution.solution_id,
            reporter_id=uuid4(),
            created_at=now - timedelta(days=2),
        )
    # 2 more distinct reporters at 15 days ago (in 30d but not 7d)
    for _ in range(2):
        _seed_outcome(
            service,
            session,
            solution_id=solution.solution_id,
            reporter_id=uuid4(),
            created_at=now - timedelta(days=15),
        )

    metrics = service._outcomes.aggregate_usage_metrics(now)
    assert metrics["unique_reporters_total"] == 5
    assert metrics["unique_reporters_7d"] == 3
    assert metrics["unique_reporters_30d"] == 5


# ---------------------------------------------------------------------------
# OutcomeRepository.outcome_counts_by_solution_ids
# ---------------------------------------------------------------------------


def test_outcome_counts_by_solution_ids_empty_input_returns_empty(
    service,
) -> None:
    """SQL path must not issue a ``WHERE … IN ()`` for empty input —
    short-circuit to ``{}`` before hitting the session."""
    assert service._outcomes.outcome_counts_by_solution_ids([]) == {}


def test_outcome_counts_by_solution_ids_groups_by_solution(service, session) -> None:
    now = datetime.now(tz=UTC)
    problem = _seed_problem(service)
    s1 = _seed_solution(service, problem.problem_id)
    s2 = _seed_solution(service, problem.problem_id)
    reporter = uuid4()

    for _ in range(5):
        _seed_outcome(
            service,
            session,
            solution_id=s1.solution_id,
            reporter_id=reporter,
            created_at=now,
        )
    for _ in range(2):
        _seed_outcome(
            service,
            session,
            solution_id=s2.solution_id,
            reporter_id=reporter,
            created_at=now,
        )

    counts = service._outcomes.outcome_counts_by_solution_ids(
        [s1.solution_id, s2.solution_id]
    )
    assert counts == {s1.solution_id: 5, s2.solution_id: 2}


def test_outcome_counts_by_solution_ids_omits_missing(service, session) -> None:
    """Solutions with zero outcomes are absent from the dict, not mapped to 0."""
    now = datetime.now(tz=UTC)
    problem = _seed_problem(service)
    s_with = _seed_solution(service, problem.problem_id)
    s_without = _seed_solution(service, problem.problem_id)
    reporter = uuid4()

    _seed_outcome(
        service,
        session,
        solution_id=s_with.solution_id,
        reporter_id=reporter,
        created_at=now,
    )

    counts = service._outcomes.outcome_counts_by_solution_ids(
        [s_with.solution_id, s_without.solution_id]
    )
    assert counts == {s_with.solution_id: 1}
    assert s_without.solution_id not in counts


# ---------------------------------------------------------------------------
# Service.get_usage_dashboard end-to-end against PostgreSQL
# ---------------------------------------------------------------------------


def test_get_usage_dashboard_end_to_end(service, session) -> None:
    """Cross-table join (problem→solutions→outcomes) returns ranked top
    list when run against a real Postgres backend."""
    now = datetime.now(tz=UTC)
    reporter = uuid4()

    expected_counts = (5, 2, 1)
    seeded = []
    for outcome_count in expected_counts:
        problem = _seed_problem(service)
        solution = _seed_solution(service, problem.problem_id)
        for _ in range(outcome_count):
            _seed_outcome(
                service,
                session,
                solution_id=solution.solution_id,
                reporter_id=reporter,
                created_at=now,
            )
        seeded.append((problem.problem_id, outcome_count))

    # One more problem with no outcomes — should not appear in top list.
    p_zero = _seed_problem(service)
    _seed_solution(service, p_zero.problem_id)

    dashboard = service.get_usage_dashboard()
    assert dashboard["problems"]["total_approved"] == 4
    assert dashboard["problems"]["with_outcomes"] == 3
    assert dashboard["problems"]["with_zero_outcomes"] == 1

    top = dashboard["top_problems_by_outcomes"]
    assert len(top) == 3
    assert tuple(t["outcome_count"] for t in top) == expected_counts
    assert {t["problem_id"] for t in top} == {str(pid) for pid, _ in seeded}
