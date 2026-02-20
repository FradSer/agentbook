from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.models import Outcome, Problem, Solution
from app.infrastructure.persistence.sqlalchemy_models import (
    OutcomeORM,
    ProblemORM,
    SolutionORM,
    parse_uuid,
)

try:
    from pgvector.sqlalchemy import Vector
except Exception:  # pragma: no cover
    Vector = None

SessionFactory = Callable[[], Session]


def _to_problem_domain(row: ProblemORM) -> Problem:
    embedding = None
    if row.embedding is not None:
        try:
            embedding = [float(v) for v in row.embedding]
        except (TypeError, ValueError):
            embedding = None
    return Problem(
        problem_id=parse_uuid(row.problem_id),
        author_id=parse_uuid(row.author_id),
        description=row.description,
        error_signature=row.error_signature,
        environment=row.environment,
        tags=list(row.tags) if row.tags else None,
        embedding=embedding,
        best_confidence=row.best_confidence,
        solution_count=row.solution_count,
        created_at=row.created_at,
        last_activity_at=row.last_activity_at,
    )


def _to_solution_domain(row: SolutionORM) -> Solution:
    return Solution(
        solution_id=parse_uuid(row.solution_id),
        problem_id=parse_uuid(row.problem_id),
        author_id=parse_uuid(row.author_id),
        content=row.content,
        steps=list(row.steps) if row.steps else [],
        author_verified=row.author_verified,
        confidence=row.confidence,
        outcome_count=row.outcome_count,
        success_count=row.success_count,
        failure_count=row.failure_count,
        environment_scores=dict(row.environment_scores) if row.environment_scores else {},
        canonical_id=parse_uuid(row.canonical_id) if row.canonical_id else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_outcome_domain(row: OutcomeORM) -> Outcome:
    return Outcome(
        outcome_id=parse_uuid(row.outcome_id),
        solution_id=parse_uuid(row.solution_id),
        reporter_id=parse_uuid(row.reporter_id),
        success=row.success,
        environment=row.environment,
        error_after=row.error_after,
        time_saved_seconds=row.time_saved_seconds,
        notes=row.notes,
        weight=row.weight,
        created_at=row.created_at,
    )


class SQLAlchemyProblemRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def add(self, problem: Problem) -> None:
        with self._session_factory() as session:
            existing = session.get(ProblemORM, str(problem.problem_id))
            if existing is None:
                existing = ProblemORM(problem_id=str(problem.problem_id))
            existing.author_id = str(problem.author_id)
            existing.description = problem.description
            existing.error_signature = problem.error_signature
            existing.environment = problem.environment
            existing.tags = problem.tags
            existing.embedding = problem.embedding
            existing.best_confidence = problem.best_confidence
            existing.solution_count = problem.solution_count
            existing.created_at = problem.created_at
            existing.last_activity_at = problem.last_activity_at
            session.merge(existing)
            session.flush()

    def get(self, problem_id: UUID) -> Problem | None:
        with self._session_factory() as session:
            row = session.get(ProblemORM, str(problem_id))
            return None if row is None else _to_problem_domain(row)

    def list_all(self) -> list[Problem]:
        with self._session_factory() as session:
            rows = session.execute(select(ProblemORM)).scalars().all()
            return [_to_problem_domain(r) for r in rows]

    def find_by_error_signature(self, signature: str) -> Problem | None:
        with self._session_factory() as session:
            stmt = select(ProblemORM).where(ProblemORM.error_signature == signature)
            row = session.execute(stmt).scalar_one_or_none()
            return None if row is None else _to_problem_domain(row)

    def find_similar(self, embedding: list[float], threshold: float) -> list[Problem]:
        with self._session_factory() as session:
            if Vector is None or not embedding:
                return []
            distance_expr = ProblemORM.embedding.cosine_distance(embedding)
            stmt = (
                select(ProblemORM)
                .where(ProblemORM.embedding.is_not(None))
                .where(distance_expr < (1.0 - threshold))
                .order_by(distance_expr)
                .limit(10)
            )
            rows = session.execute(stmt).scalars().all()
            return [_to_problem_domain(r) for r in rows]

    def update(self, problem: Problem) -> None:
        self.add(problem)


class SQLAlchemySolutionRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def add(self, solution: Solution) -> None:
        with self._session_factory() as session:
            existing = session.get(SolutionORM, str(solution.solution_id))
            if existing is None:
                existing = SolutionORM(solution_id=str(solution.solution_id))
            existing.problem_id = str(solution.problem_id)
            existing.author_id = str(solution.author_id)
            existing.content = solution.content
            existing.steps = solution.steps
            existing.author_verified = solution.author_verified
            existing.confidence = solution.confidence
            existing.outcome_count = solution.outcome_count
            existing.success_count = solution.success_count
            existing.failure_count = solution.failure_count
            existing.environment_scores = solution.environment_scores
            existing.canonical_id = str(solution.canonical_id) if solution.canonical_id else None
            existing.created_at = solution.created_at
            existing.updated_at = solution.updated_at
            session.merge(existing)
            session.flush()

    def get(self, solution_id: UUID) -> Solution | None:
        with self._session_factory() as session:
            row = session.get(SolutionORM, str(solution_id))
            return None if row is None else _to_solution_domain(row)

    def list_by_problem(self, problem_id: UUID) -> list[Solution]:
        with self._session_factory() as session:
            stmt = (
                select(SolutionORM)
                .where(SolutionORM.problem_id == str(problem_id))
                .order_by(SolutionORM.confidence.desc())
            )
            rows = session.execute(stmt).scalars().all()
            return [_to_solution_domain(r) for r in rows]

    def find_canonical_candidates(
        self, problem_id: UUID, similarity_threshold: float
    ) -> list[Solution]:
        with self._session_factory() as session:
            stmt = (
                select(SolutionORM)
                .where(SolutionORM.problem_id == str(problem_id))
                .where(SolutionORM.canonical_id.is_(None))
            )
            rows = session.execute(stmt).scalars().all()
            return [_to_solution_domain(r) for r in rows]

    def update(self, solution: Solution) -> None:
        self.add(solution)


class SQLAlchemyOutcomeRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def add(self, outcome: Outcome) -> None:
        with self._session_factory() as session:
            row = OutcomeORM(
                outcome_id=str(outcome.outcome_id),
                solution_id=str(outcome.solution_id),
                reporter_id=str(outcome.reporter_id),
                success=outcome.success,
                environment=outcome.environment,
                error_after=outcome.error_after,
                time_saved_seconds=outcome.time_saved_seconds,
                notes=outcome.notes,
                weight=outcome.weight,
                created_at=outcome.created_at,
            )
            session.add(row)
            session.flush()

    def list_by_solution(self, solution_id: UUID) -> list[Outcome]:
        with self._session_factory() as session:
            stmt = (
                select(OutcomeORM)
                .where(OutcomeORM.solution_id == str(solution_id))
                .order_by(OutcomeORM.created_at.desc())
            )
            rows = session.execute(stmt).scalars().all()
            return [_to_outcome_domain(r) for r in rows]

    def count_by_reporter(self, reporter_id: UUID, since: datetime) -> int:
        with self._session_factory() as session:
            stmt = (
                select(func.count())
                .select_from(OutcomeORM)
                .where(OutcomeORM.reporter_id == str(reporter_id))
                .where(OutcomeORM.created_at >= since)
            )
            return session.execute(stmt).scalar_one()
