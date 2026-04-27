from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from backend.domain.models import (
    Agent,
    Outcome,
    Problem,
    ResearchCycle,
    Solution,
)
from backend.infrastructure.persistence.sqlalchemy_models import (
    AgentORM,
    OutcomeORM,
    ProblemORM,
    ResearchCycleORM,
    SolutionORM,
    parse_uuid,
)

try:
    from pgvector.sqlalchemy import Vector
except Exception:  # pragma: no cover
    Vector = None

SessionFactory = Callable[[], Session]


def _to_agent_domain(row: AgentORM) -> Agent:
    return Agent(
        agent_id=parse_uuid(row.agent_id),
        api_key_hash=row.api_key_hash,
        model_type=row.model_type,
        created_at=row.created_at,
        last_active_at=row.last_active_at,
    )


class SQLAlchemyAgentRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def add(self, agent: Agent) -> None:
        with self._session_factory() as session:
            existing = session.get(AgentORM, str(agent.agent_id))
            if existing is None:
                existing = AgentORM(agent_id=str(agent.agent_id))
            existing.api_key_hash = agent.api_key_hash
            existing.model_type = agent.model_type
            existing.created_at = agent.created_at
            existing.last_active_at = agent.last_active_at
            session.merge(existing)
            session.commit()

    def get(self, agent_id: UUID) -> Agent | None:
        with self._session_factory() as session:
            row = session.get(AgentORM, str(agent_id))
            if row is None:
                return None
            return _to_agent_domain(row)

    def get_by_api_key_hash(self, api_key_hash: str) -> Agent | None:
        with self._session_factory() as session:
            statement = select(AgentORM).where(AgentORM.api_key_hash == api_key_hash)
            row = session.execute(statement).scalar_one_or_none()
            if row is None:
                return None
            return _to_agent_domain(row)


def _to_problem_domain(row: ProblemORM) -> Problem:
    return Problem(
        problem_id=parse_uuid(row.problem_id),
        author_id=parse_uuid(row.author_id),
        description=row.description,
        error_signature=row.error_signature,
        environment=row.environment,
        tags=list(row.tags) if row.tags else None,
        embedding=row.embedding,
        best_confidence=row.best_confidence,
        solution_count=row.solution_count,
        version=row.version,
        created_at=row.created_at,
        last_activity_at=row.last_activity_at,
        review_status=getattr(row, "review_status", None),
        canonical_solution_id=parse_uuid(row.canonical_solution_id)
        if getattr(row, "canonical_solution_id", None)
        else None,
        research_started_at=getattr(row, "research_started_at", None),
    )


def _to_solution_domain(row: SolutionORM) -> Solution:
    return Solution(
        problem_id=parse_uuid(row.problem_id),
        author_id=parse_uuid(row.author_id),
        content=row.content,
        steps=list(row.steps) if row.steps else [],
        confidence=row.confidence,
        outcome_count=row.outcome_count,
        success_count=row.success_count,
        failure_count=row.failure_count,
        canonical_id=parse_uuid(row.canonical_id) if row.canonical_id else None,
        parent_solution_id=parse_uuid(row.parent_solution_id)
        if row.parent_solution_id
        else None,
        promotion_status=getattr(row, "promotion_status", None),
        review_status=getattr(row, "review_status", None),
        review_score=getattr(row, "review_score", None),
        reviewed_at=getattr(row, "reviewed_at", None),
        solution_id=parse_uuid(row.solution_id),
        created_at=row.created_at,
        updated_at=row.updated_at,
        llm_model=getattr(row, "llm_model", None),
    )


def _to_outcome_domain(row: OutcomeORM) -> Outcome:
    if not row.kind:
        raise ValueError("Outcome kind cannot be null")
    return Outcome(
        outcome_id=parse_uuid(row.outcome_id),
        solution_id=parse_uuid(row.solution_id),
        reporter_id=parse_uuid(row.reporter_id),
        success=row.success,
        kind=row.kind,
        environment=row.environment,
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
            existing.version = problem.version
            existing.created_at = problem.created_at
            existing.last_activity_at = problem.last_activity_at
            existing.review_status = problem.review_status
            existing.canonical_solution_id = (
                str(problem.canonical_solution_id)
                if problem.canonical_solution_id
                else None
            )
            session.merge(existing)
            session.commit()

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

    def _vector_query(self, session, embedding: list[float]) -> tuple | None:
        """Build base cosine-distance query. Returns (distance_expr, base_stmt) or None."""
        if session.bind is None or session.bind.dialect.name != "postgresql":
            return None
        distance_expr = ProblemORM.embedding.cosine_distance(embedding)
        base = (
            select(ProblemORM)
            .where(ProblemORM.embedding.is_not(None))
            .order_by(distance_expr)
        )
        return distance_expr, base

    def find_similar(self, embedding: list[float], threshold: float) -> list[Problem]:
        if Vector is None or not embedding:
            return []
        with self._session_factory() as session:
            try:
                result = self._vector_query(session, embedding)
                if result is None:
                    return []
                distance_expr, base = result
                stmt = base.where(distance_expr < (1.0 - threshold)).limit(10)
                rows = session.execute(stmt).scalars().all()
                return [_to_problem_domain(r) for r in rows]
            except Exception:
                return []

    def find_similar_scored(
        self, query_embedding: list[float]
    ) -> list[tuple[Problem, float]]:
        if Vector is None or not query_embedding:
            return []
        with self._session_factory() as session:
            try:
                result = self._vector_query(session, query_embedding)
                if result is None:
                    return []
                distance_expr, base = result
                stmt = (
                    base.add_columns((1.0 - distance_expr).label("similarity"))
                    .where(ProblemORM.review_status == "approved")
                    .limit(20)
                )
                rows = session.execute(stmt).all()
                return [(_to_problem_domain(r[0]), float(r[1])) for r in rows]
            except Exception:
                return []

    def find_hybrid(
        self,
        query_embedding: list[float] | None,
        query_text: str,
        limit: int,
    ) -> list[tuple[Problem, float]]:
        from backend.application._rrf import rrf_fuse

        candidate_pool = max(limit, 50)
        dense: list[Problem] = []
        sparse: list[Problem] = []

        with self._session_factory() as session:
            if session.bind is None or session.bind.dialect.name != "postgresql":
                return []

            if query_embedding and Vector is not None:
                try:
                    dense_stmt = (
                        select(ProblemORM)
                        .where(
                            ProblemORM.review_status == "approved",
                            ProblemORM.embedding.is_not(None),
                        )
                        .order_by(ProblemORM.embedding.cosine_distance(query_embedding))
                        .limit(candidate_pool)
                    )
                    dense = [
                        _to_problem_domain(row)
                        for row in session.execute(dense_stmt).scalars().all()
                    ]
                except (ProgrammingError, OperationalError):
                    dense = []

            if query_text:
                try:
                    searchable = func.concat_ws(
                        " ",
                        ProblemORM.description,
                        ProblemORM.error_signature,
                    )
                    tsv = func.to_tsvector("english", searchable)
                    tsq = func.plainto_tsquery("english", query_text)
                    sparse_stmt = (
                        select(ProblemORM)
                        .where(
                            ProblemORM.review_status == "approved",
                            tsv.op("@@")(tsq),
                        )
                        .order_by(func.ts_rank(tsv, tsq).desc())
                        .limit(candidate_pool)
                    )
                    sparse = [
                        _to_problem_domain(row)
                        for row in session.execute(sparse_stmt).scalars().all()
                    ]
                except (ProgrammingError, OperationalError):
                    sparse = []

        if not dense and not sparse:
            return []
        return rrf_fuse([dense, sparse], k=60, limit=limit)

    def update(self, problem: Problem) -> None:
        """Update problem with optimistic locking."""
        from backend.application.errors import ConcurrentModificationError

        with self._session_factory() as session:
            existing = session.get(ProblemORM, str(problem.problem_id))
            if existing is None:
                raise ValueError(f"Problem {problem.problem_id} not found")

            # Check version for optimistic locking
            if existing.version != problem.version:
                raise ConcurrentModificationError(
                    f"Problem {problem.problem_id} was modified by another process. "
                    f"Expected version {problem.version}, found {existing.version}"
                )

            # Update fields and increment version
            existing.author_id = str(problem.author_id)
            existing.description = problem.description
            existing.error_signature = problem.error_signature
            existing.environment = problem.environment
            existing.tags = problem.tags
            existing.embedding = problem.embedding
            existing.best_confidence = problem.best_confidence
            existing.solution_count = problem.solution_count
            existing.version = problem.version + 1
            existing.created_at = problem.created_at
            existing.last_activity_at = problem.last_activity_at
            existing.review_status = problem.review_status
            existing.canonical_solution_id = (
                str(problem.canonical_solution_id)
                if problem.canonical_solution_id
                else None
            )
            existing.research_started_at = problem.research_started_at
            session.merge(existing)
            session.commit()

    def find_unreviewed(
        self,
        limit: int,
        retry_error_before: datetime | None = None,
    ) -> list[Problem]:
        with self._session_factory() as session:
            pending_clause = ProblemORM.review_status.is_(None)
            if retry_error_before is not None:
                error_clause = (ProblemORM.review_status == "error") & (
                    (ProblemORM.reviewed_at.is_(None))
                    | (ProblemORM.reviewed_at <= retry_error_before)
                )
                where_clause = pending_clause | error_clause
            else:
                where_clause = pending_clause
            stmt = (
                select(ProblemORM)
                .where(where_clause)
                .order_by(ProblemORM.created_at.desc())
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [_to_problem_domain(r) for r in rows]

    def find_research_candidates(
        self, limit: int = 10, offset: int = 0, max_confidence: float = 1.0
    ) -> list[Problem]:
        with self._session_factory() as session:
            stmt = (
                select(ProblemORM)
                .where(ProblemORM.review_status == "approved")
                .where(ProblemORM.best_confidence < max_confidence)
                .order_by(
                    ProblemORM.solution_count.asc(), ProblemORM.best_confidence.asc()
                )
                .offset(offset)
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [_to_problem_domain(r) for r in rows]

    def delete(self, problem_id: UUID) -> None:
        with self._session_factory() as session:
            row = session.get(ProblemORM, str(problem_id))
            if row is not None:
                session.delete(row)
                session.commit()


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
            existing.confidence = solution.confidence
            existing.outcome_count = solution.outcome_count
            existing.success_count = solution.success_count
            existing.failure_count = solution.failure_count
            existing.canonical_id = (
                str(solution.canonical_id) if solution.canonical_id else None
            )
            existing.parent_solution_id = (
                str(solution.parent_solution_id)
                if solution.parent_solution_id
                else None
            )
            existing.promotion_status = solution.promotion_status
            existing.created_at = solution.created_at
            existing.updated_at = solution.updated_at
            existing.review_status = solution.review_status
            existing.review_score = solution.review_score
            existing.reviewed_at = solution.reviewed_at
            existing.llm_model = solution.llm_model
            session.merge(existing)
            session.commit()

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

    def update(self, solution: Solution) -> None:
        self.add(solution)

    def list_by_problem_ranked(self, problem_id: UUID) -> list[Solution]:
        with self._session_factory() as session:
            stmt = (
                select(SolutionORM)
                .where(SolutionORM.problem_id == str(problem_id))
                .order_by(
                    SolutionORM.canonical_id.is_(None).desc(),
                    SolutionORM.confidence.desc(),
                )
            )
            rows = session.execute(stmt).scalars().all()
            return [_to_solution_domain(r) for r in rows]

    def find_unreviewed(
        self,
        limit: int,
        retry_error_before: datetime | None = None,
    ) -> list[Solution]:
        with self._session_factory() as session:
            pending_clause = SolutionORM.review_status.is_(None)
            if retry_error_before is not None:
                error_clause = (SolutionORM.review_status == "error") & (
                    (SolutionORM.reviewed_at.is_(None))
                    | (SolutionORM.reviewed_at <= retry_error_before)
                )
                where_clause = pending_clause | error_clause
            else:
                where_clause = pending_clause
            stmt = (
                select(SolutionORM)
                .where(where_clause)
                .order_by(SolutionORM.created_at.desc())
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [_to_solution_domain(r) for r in rows]

    def find_superseded(self, problem_id: UUID) -> list[Solution]:
        with self._session_factory() as session:
            stmt = (
                select(SolutionORM)
                .where(SolutionORM.problem_id == str(problem_id))
                .where(SolutionORM.canonical_id.is_not(None))
            )
            rows = session.execute(stmt).scalars().all()
            return [_to_solution_domain(r) for r in rows]

    def delete(self, solution_id: UUID) -> None:
        with self._session_factory() as session:
            row = session.get(SolutionORM, str(solution_id))
            if row is not None:
                session.delete(row)
                session.commit()


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
                time_saved_seconds=outcome.time_saved_seconds,
                notes=outcome.notes,
                weight=outcome.weight,
                created_at=outcome.created_at,
            )
            session.add(row)
            session.commit()

    def list_by_solution(self, solution_id: UUID) -> list[Outcome]:
        with self._session_factory() as session:
            stmt = (
                select(OutcomeORM)
                .where(OutcomeORM.solution_id == str(solution_id))
                .order_by(OutcomeORM.created_at.desc())
            )
            rows = session.execute(stmt).scalars().all()
            return [_to_outcome_domain(r) for r in rows]

    def list_by_problem(
        self, problem_id: UUID, solution_ids: list[UUID]
    ) -> list[Outcome]:
        if not solution_ids:
            return []
        with self._session_factory() as session:
            str_ids = [str(sid) for sid in solution_ids]
            stmt = (
                select(OutcomeORM)
                .where(OutcomeORM.solution_id.in_(str_ids))
                .order_by(OutcomeORM.created_at.asc())
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

    def list_by_reporter(self, reporter_id: UUID) -> list[Outcome]:
        with self._session_factory() as session:
            stmt = (
                select(OutcomeORM)
                .where(OutcomeORM.reporter_id == str(reporter_id))
                .order_by(OutcomeORM.created_at.desc())
            )
            rows = session.execute(stmt).scalars().all()
            return [_to_outcome_domain(r) for r in rows]


def _to_research_cycle_domain(row: ResearchCycleORM) -> ResearchCycle:
    return ResearchCycle(
        problem_id=parse_uuid(row.problem_id),
        researcher_id=parse_uuid(row.researcher_id),
        proposed_solution_id=parse_uuid(row.proposed_solution_id)
        if row.proposed_solution_id
        else None,
        previous_best_confidence=row.previous_best_confidence,
        new_confidence=row.new_confidence,
        status=row.status,
        reasoning=row.reasoning,
        cycle_id=parse_uuid(row.cycle_id),
        created_at=row.created_at,
        llm_model=getattr(row, "llm_model", None),
    )


class SQLAlchemyResearchCycleRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def add(self, cycle: ResearchCycle) -> None:
        with self._session_factory() as session:
            row = ResearchCycleORM(
                cycle_id=str(cycle.cycle_id),
                problem_id=str(cycle.problem_id),
                researcher_id=str(cycle.researcher_id),
                proposed_solution_id=str(cycle.proposed_solution_id)
                if cycle.proposed_solution_id
                else None,
                previous_best_confidence=cycle.previous_best_confidence,
                new_confidence=cycle.new_confidence,
                status=cycle.status,
                reasoning=cycle.reasoning,
                llm_model=cycle.llm_model,
                created_at=cycle.created_at,
            )
            session.add(row)
            session.commit()

    def list_by_problem(self, problem_id: UUID) -> list[ResearchCycle]:
        with self._session_factory() as session:
            stmt = (
                select(ResearchCycleORM)
                .where(ResearchCycleORM.problem_id == str(problem_id))
                .order_by(ResearchCycleORM.created_at.desc())
            )
            rows = session.execute(stmt).scalars().all()
            return [_to_research_cycle_domain(r) for r in rows]

    def count_by_researcher(self, researcher_id: UUID, since: datetime) -> int:
        with self._session_factory() as session:
            stmt = (
                select(func.count())
                .select_from(ResearchCycleORM)
                .where(ResearchCycleORM.researcher_id == str(researcher_id))
                .where(ResearchCycleORM.created_at >= since)
            )
            return session.execute(stmt).scalar_one()

    def get_last_researched_at(self, problem_id: UUID) -> datetime | None:
        with self._session_factory() as session:
            stmt = select(func.max(ResearchCycleORM.created_at)).where(
                ResearchCycleORM.problem_id == str(problem_id)
            )
            return session.execute(stmt).scalar_one_or_none()

    def count_consecutive_no_improvement(self, problem_id: UUID) -> int:
        with self._session_factory() as session:
            stmt = (
                select(ResearchCycleORM.status)
                .where(ResearchCycleORM.problem_id == str(problem_id))
                .order_by(ResearchCycleORM.created_at.desc())
                .limit(20)
            )
            rows = session.execute(stmt).scalars().all()
        count = 0
        for status in rows:
            if status in ("no_improvement", "no_solution_proposed"):
                count += 1
            else:
                break
        return count
