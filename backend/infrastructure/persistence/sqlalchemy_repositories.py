from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import case, func, select, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from backend.application._recurrence import compute_recurrence_rollup
from backend.application.clustering import detect_clusters
from backend.application.service import RESEARCH_TIMEOUT_SECONDS
from backend.domain.models import (
    Agent,
    Outcome,
    Problem,
    QueryEvent,
    ResearchCycle,
    Solution,
)
from backend.domain.repositories import AgentRepository
from backend.domain.search import SearchDiagnostics
from backend.infrastructure.persistence.sqlalchemy_models import (
    AgentORM,
    OutcomeORM,
    ProblemORM,
    QueryEventORM,
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
        ip_hash=row.ip_hash,
        fingerprint_hash=row.fingerprint_hash,
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
            existing.ip_hash = agent.ip_hash
            existing.fingerprint_hash = agent.fingerprint_hash
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


def _write_active_embedding(row: ProblemORM, embedding: list[float] | None) -> None:
    """Mirror of ``_read_active_embedding`` for write paths.

    During cutover (``EMBEDDING_VERSION=v1`` with ``VOYAGE_API_KEY`` set),
    service-level callers also invoke ``update_embedding_v2`` separately so
    the v2 column tracks new writes — that's the dual-write strategy. This
    helper just picks the primary column based on the active version."""
    from backend.core.config import settings

    if settings.embedding_version == "v2":
        row.embedding_v2 = embedding
    else:
        row.embedding = embedding


def _read_active_embedding(row: ProblemORM) -> list[float] | None:
    """Pick whichever embedding column the cutover flag selects.

    Falls back to the legacy column when ``embedding_v2`` is NULL during the
    backfill window — that way queries before the operator flips
    ``EMBEDDING_VERSION=v2`` continue to retrieve relevant rows even though
    they may have already had v2 embeddings written by service-level
    dual-write."""
    from backend.core.config import settings

    if settings.embedding_version == "v2":
        primary = getattr(row, "embedding_v2", None)
        if primary is not None:
            return primary
        return row.embedding
    return row.embedding


def _to_problem_domain(row: ProblemORM) -> Problem:
    return Problem(
        problem_id=parse_uuid(row.problem_id),
        author_id=parse_uuid(row.author_id),
        description=row.description,
        error_signature=row.error_signature,
        environment=row.environment,
        tags=list(row.tags) if row.tags else None,
        embedding=_read_active_embedding(row),
        best_confidence=row.best_confidence,
        solution_count=row.solution_count,
        version=row.version,
        created_at=row.created_at,
        last_activity_at=row.last_activity_at,
        review_status=getattr(row, "review_status", None),
        review_score=getattr(row, "review_score", None),
        reviewed_at=getattr(row, "reviewed_at", None),
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
        root_cause_pattern=getattr(row, "root_cause_pattern", None),
        localization_cues=list(getattr(row, "localization_cues", None) or []),
        verification=list(getattr(row, "verification", None) or []),
        root_cause_class=getattr(row, "root_cause_class", None),
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
        error_after=getattr(row, "error_after", None),
        time_saved_seconds=row.time_saved_seconds,
        notes=row.notes,
        weight=row.weight,
        created_at=row.created_at,
    )


def _orm_from_outcome(outcome: Outcome) -> OutcomeORM:
    """Build an ORM row from a domain Outcome.

    Single source of truth for the column→field mapping so adding a
    column doesn't have to be threaded through every write path
    (``add``, ``upsert``, future bulk-loaders).
    """
    return OutcomeORM(
        outcome_id=str(outcome.outcome_id),
        solution_id=str(outcome.solution_id),
        reporter_id=str(outcome.reporter_id),
        success=outcome.success,
        kind=outcome.kind,
        environment=outcome.environment,
        error_after=outcome.error_after,
        time_saved_seconds=outcome.time_saved_seconds,
        notes=outcome.notes,
        weight=outcome.weight,
        created_at=outcome.created_at,
    )


class SQLAlchemyProblemRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory
        self._retrieval_status_cache: tuple[str, bool] | None = None

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
            _write_active_embedding(existing, problem.embedding)
            existing.best_confidence = problem.best_confidence
            existing.solution_count = problem.solution_count
            existing.version = problem.version
            existing.created_at = problem.created_at
            existing.last_activity_at = problem.last_activity_at
            existing.review_status = problem.review_status
            existing.review_score = problem.review_score
            existing.reviewed_at = problem.reviewed_at
            existing.research_started_at = problem.research_started_at
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

    def _active_embedding_column(self):
        """Return the ORM column matching ``settings.embedding_version``.

        ``v1`` reads/writes ``problems.embedding`` (legacy 1536-dim).
        ``v2`` reads/writes ``problems.embedding_v2`` (Voyage v3-large 1024-dim,
        added by the ``add_embedding_v2_column`` Alembic migration).

        Centralised so ``find_similar``, ``find_similar_scored`` and
        ``find_hybrid`` cannot drift apart during the cutover window — every
        vector query path resolves to the same column on every call."""
        from backend.core.config import settings

        return (
            ProblemORM.embedding_v2
            if settings.embedding_version == "v2"
            else ProblemORM.embedding
        )

    def _vector_query(self, session, embedding: list[float]) -> tuple | None:
        """Build base cosine-distance query. Returns (distance_expr, base_stmt) or None."""
        if session.bind is None or session.bind.dialect.name != "postgresql":
            return None
        column = self._active_embedding_column()
        distance_expr = column.cosine_distance(embedding)
        base = select(ProblemORM).where(column.is_not(None)).order_by(distance_expr)
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
        results, _ = self.find_hybrid_with_diagnostics(
            query_embedding=query_embedding,
            query_text=query_text,
            limit=limit,
        )
        return results

    def retrieval_status(self) -> tuple[str, bool]:
        """Report ``(backend, pgvector_available)`` without a search round-trip.

        Memoised after the first successful resolution: pgvector install
        state is process-lifetime stable (the extension is installed at
        boot or it isn't), so a single ``pg_extension`` probe is enough.
        ``Vector is None`` short-circuits to "adapter unavailable"
        because the dense leg is permanently dark even if the server
        has the extension loaded.
        """
        if self._retrieval_status_cache is not None:
            return self._retrieval_status_cache
        result = self._probe_retrieval_status()
        # Only memoise terminal answers — a transient connection error
        # leaves it None so the next health-poll re-probes.
        if result is not None:
            self._retrieval_status_cache = result
            return result
        return ("postgres", False)

    def _probe_retrieval_status(self) -> tuple[str, bool] | None:
        """Probe ``(backend, dense_search_available)``.

        ``dense_search_available`` is true only when the pgvector adapter
        imports, the extension is installed, AND the active embedding column
        is actually a ``vector`` type. agentbook stores embeddings as JSON
        (see ``FlexibleVector``), so the dense leg stays dark even on a
        pgvector-enabled host — the column type, not mere extension
        presence, is what decides whether cosine search can run. Reporting
        extension presence alone made ``/v1/health-metrics`` claim
        ``pgvector_available: true`` while every dense query silently
        degraded to the lexical leg.
        """
        from backend.core.config import settings

        if Vector is None:
            return ("postgres", False)
        column_name = (
            "embedding_v2" if settings.embedding_version == "v2" else "embedding"
        )
        with self._session_factory() as session:
            if session.bind is None or session.bind.dialect.name != "postgresql":
                return ("unavailable", False)
            try:
                installed = session.execute(
                    text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
                ).scalar()
                if installed is None:
                    return ("postgres", False)
                column_udt = session.execute(
                    text(
                        "SELECT udt_name FROM information_schema.columns "
                        "WHERE table_name = 'problems' AND column_name = :col"
                    ),
                    {"col": column_name},
                ).scalar()
                return ("postgres", column_udt == "vector")
            except (ProgrammingError, OperationalError):
                return None

    def find_hybrid_with_diagnostics(
        self,
        query_embedding: list[float] | None,
        query_text: str,
        limit: int,
    ) -> tuple[list[tuple[Problem, float]], SearchDiagnostics]:
        from backend.domain.search import rrf_fuse

        candidate_pool = max(limit, 50)
        dense: list[Problem] = []
        sparse: list[Problem] = []
        # ``Vector is None`` means the pgvector adapter could not be
        # imported (extension not installed in this environment). Without
        # this signal the dense leg silently no-ops and the response
        # looks identical to a normal hybrid hit.
        pgvector_available = Vector is not None

        with self._session_factory() as session:
            if session.bind is None or session.bind.dialect.name != "postgresql":
                return [], SearchDiagnostics(
                    backend="unavailable",
                    pgvector_available=False,
                    dense_hits=0,
                    sparse_hits=0,
                )

            if query_embedding and pgvector_available:
                try:
                    column = self._active_embedding_column()
                    dense_stmt = (
                        select(ProblemORM)
                        .where(
                            ProblemORM.review_status == "approved",
                            column.is_not(None),
                        )
                        .order_by(column.cosine_distance(query_embedding))
                        .limit(candidate_pool)
                    )
                    dense = [
                        _to_problem_domain(row)
                        for row in session.execute(dense_stmt).scalars().all()
                    ]
                except (ProgrammingError, OperationalError):
                    # Extension was loadable as a Python adapter but the
                    # database itself can't run cosine_distance — treat as
                    # unavailable so the service can label it.
                    dense = []
                    pgvector_available = False

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

        diagnostics = SearchDiagnostics(
            backend="postgres",
            pgvector_available=pgvector_available,
            dense_hits=len(dense),
            sparse_hits=len(sparse),
        )
        if not dense and not sparse:
            return [], diagnostics
        return rrf_fuse([dense, sparse], k=60, limit=limit), diagnostics

    def update(self, problem: Problem) -> None:
        """Update problem with optimistic locking."""
        from backend.domain.errors import ConcurrentModificationError

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
            _write_active_embedding(existing, problem.embedding)
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

    def update_embedding_v2(
        self, problem_id: UUID, embedding: list[float] | None
    ) -> None:
        """Write only the ``embedding_v2`` column for an existing problem.

        Used by:

        * ``backend/scripts/reembed_corpus.py`` — bulk backfill from Voyage.
        * ``AgentbookService`` dual-write during the
          ``EMBEDDING_VERSION=v1`` window with ``VOYAGE_API_KEY`` set, so new
          problems land both columns simultaneously and the eventual flip is
          a no-op for new rows.

        Does NOT bump ``version`` — this is a side-channel write that should
        never trigger optimistic-lock contention with the primary write
        path."""
        with self._session_factory() as session:
            existing = session.get(ProblemORM, str(problem_id))
            if existing is None:
                return
            existing.embedding_v2 = embedding
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

    def list_being_researched(
        self, timeout_seconds: int = RESEARCH_TIMEOUT_SECONDS
    ) -> list[Problem]:
        with self._session_factory() as session:
            # Server-side interval keeps clock skew off the application layer;
            # PostgreSQL `make_interval(secs => :timeout_seconds)`.
            interval = func.make_interval(0, 0, 0, 0, 0, 0, timeout_seconds)
            stmt = (
                select(ProblemORM)
                .where(ProblemORM.research_started_at.isnot(None))
                .where(ProblemORM.research_started_at > func.now() - interval)
                .order_by(ProblemORM.research_started_at.desc())
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
            existing.root_cause_pattern = solution.root_cause_pattern
            existing.localization_cues = solution.localization_cues
            existing.verification = solution.verification
            existing.root_cause_class = solution.root_cause_class
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

    def list_solution_ids_by_problem_ids(
        self, problem_ids: list[UUID]
    ) -> dict[UUID, list[UUID]]:
        if not problem_ids:
            return {}
        with self._session_factory() as session:
            str_ids = [str(pid) for pid in problem_ids]
            stmt = select(SolutionORM.problem_id, SolutionORM.solution_id).where(
                SolutionORM.problem_id.in_(str_ids)
            )
            out: dict[UUID, list[UUID]] = {pid: [] for pid in problem_ids}
            for problem_id_str, solution_id_str in session.execute(stmt).all():
                pid = parse_uuid(problem_id_str)
                if pid in out:
                    out[pid].append(parse_uuid(solution_id_str))
            return out

    def list_by_problem_ids(
        self, problem_ids: list[UUID]
    ) -> dict[UUID, list[Solution]]:
        if not problem_ids:
            return {}
        with self._session_factory() as session:
            str_ids = [str(pid) for pid in problem_ids]
            stmt = select(SolutionORM).where(SolutionORM.problem_id.in_(str_ids))
            rows = session.execute(stmt).scalars().all()
            out: dict[UUID, list[Solution]] = {pid: [] for pid in problem_ids}
            for row in rows:
                pid = parse_uuid(row.problem_id)
                if pid in out:
                    out[pid].append(_to_solution_domain(row))
            return out

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
            session.add(_orm_from_outcome(outcome))
            session.commit()

    def upsert(self, outcome: Outcome) -> tuple[Outcome, bool]:
        """Update by ``(solution_id, reporter_id)`` if present, else insert.

        Bound by the ``uq_outcome_reporter_solution`` UniqueConstraint
        added in migration ``p1q2r3s4t5u6_outcome_reporter_solution_unique``;
        this method is the only safe write path once that constraint is
        live.
        """
        with self._session_factory() as session:
            existing = (
                session.query(OutcomeORM)
                .filter(
                    OutcomeORM.solution_id == str(outcome.solution_id),
                    OutcomeORM.reporter_id == str(outcome.reporter_id),
                )
                .one_or_none()
            )
            if existing is None:
                session.add(_orm_from_outcome(outcome))
                session.commit()
                return outcome, True

            existing.success = outcome.success
            existing.kind = outcome.kind
            existing.weight = outcome.weight
            existing.environment = outcome.environment
            existing.notes = outcome.notes
            existing.time_saved_seconds = outcome.time_saved_seconds
            existing.error_after = outcome.error_after
            existing.created_at = outcome.created_at
            session.commit()
            return _to_outcome_domain(existing), False

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

    def oldest_created_at_by_reporter(
        self, reporter_id: UUID, since: datetime
    ) -> datetime | None:
        with self._session_factory() as session:
            stmt = (
                select(func.min(OutcomeORM.created_at))
                .where(OutcomeORM.reporter_id == str(reporter_id))
                .where(OutcomeORM.created_at >= since)
            )
            return session.execute(stmt).scalar()

    def list_by_reporter(self, reporter_id: UUID) -> list[Outcome]:
        with self._session_factory() as session:
            stmt = (
                select(OutcomeORM)
                .where(OutcomeORM.reporter_id == str(reporter_id))
                .order_by(OutcomeORM.created_at.desc())
            )
            rows = session.execute(stmt).scalars().all()
            return [_to_outcome_domain(r) for r in rows]

    def aggregate_usage_metrics(self, now: datetime) -> dict:
        seven_ago = now - timedelta(days=7)
        thirty_ago = now - timedelta(days=30)
        # ``count(distinct case when cond then col end)`` is the portable
        # idiom for windowed COUNT DISTINCT (Postgres FILTER is not
        # supported on SQLite). Rows outside the window evaluate to NULL
        # which DISTINCT excludes — same semantics, one round-trip.
        reporter_in_7d = case(
            (OutcomeORM.created_at >= seven_ago, OutcomeORM.reporter_id),
            else_=None,
        )
        reporter_in_30d = case(
            (OutcomeORM.created_at >= thirty_ago, OutcomeORM.reporter_id),
            else_=None,
        )
        with self._session_factory() as session:
            row = session.execute(
                select(
                    func.count().label("outcomes_total"),
                    func.coalesce(
                        func.sum(
                            case((OutcomeORM.created_at >= seven_ago, 1), else_=0)
                        ),
                        0,
                    ).label("outcomes_last_7d"),
                    func.coalesce(
                        func.sum(
                            case((OutcomeORM.created_at >= thirty_ago, 1), else_=0)
                        ),
                        0,
                    ).label("outcomes_last_30d"),
                    func.coalesce(
                        func.sum(case((OutcomeORM.kind == "verified", 1), else_=0)),
                        0,
                    ).label("verified_total"),
                    func.coalesce(
                        func.sum(case((OutcomeORM.kind == "observed", 1), else_=0)),
                        0,
                    ).label("observed_total"),
                    func.count(func.distinct(OutcomeORM.reporter_id)).label(
                        "unique_total"
                    ),
                    func.count(func.distinct(reporter_in_7d)).label("unique_7d"),
                    func.count(func.distinct(reporter_in_30d)).label("unique_30d"),
                )
            ).one()
        return {
            "outcomes_total": int(row.outcomes_total or 0),
            "outcomes_last_7d": int(row.outcomes_last_7d or 0),
            "outcomes_last_30d": int(row.outcomes_last_30d or 0),
            "verified_total": int(row.verified_total or 0),
            "observed_total": int(row.observed_total or 0),
            "unique_reporters_total": int(row.unique_total or 0),
            "unique_reporters_7d": int(row.unique_7d or 0),
            "unique_reporters_30d": int(row.unique_30d or 0),
        }

    def outcome_counts_by_solution_ids(
        self, solution_ids: list[UUID]
    ) -> dict[UUID, int]:
        if not solution_ids:
            return {}
        with self._session_factory() as session:
            str_ids = [str(sid) for sid in solution_ids]
            stmt = (
                select(OutcomeORM.solution_id, func.count())
                .where(OutcomeORM.solution_id.in_(str_ids))
                .group_by(OutcomeORM.solution_id)
            )
            rows = session.execute(stmt).all()
            return {parse_uuid(sid): int(cnt) for sid, cnt in rows}

    def list_by_solution_ids(self, solution_ids: list[UUID]) -> list[Outcome]:
        if not solution_ids:
            return []
        with self._session_factory() as session:
            str_ids = [str(sid) for sid in solution_ids]
            stmt = select(OutcomeORM).where(OutcomeORM.solution_id.in_(str_ids))
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

    def get_latest_cycle_at(self) -> datetime | None:
        with self._session_factory() as session:
            stmt = select(func.max(ResearchCycleORM.created_at))
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


def _to_query_event_domain(row: QueryEventORM) -> QueryEvent:
    return QueryEvent(
        event_id=parse_uuid(row.event_id),
        query_text=row.query_text,
        agent_id=parse_uuid(row.agent_id) if row.agent_id else None,
        ip_hash=row.ip_hash,
        fingerprint_hash=row.fingerprint_hash,
        top_match_problem_id=parse_uuid(row.problem_id) if row.problem_id else None,
        top_match_quality=row.top_match_quality,
        has_help=row.has_help,
        is_self_hit=row.is_self_hit,
        is_seed_replay=row.is_seed_replay,
        is_seeded_hit=row.is_seeded_hit,
        pattern_class_hit=row.pattern_class_hit,
        created_at=row.created_at,
    )


def _orm_from_query_event(event: QueryEvent) -> QueryEventORM:
    return QueryEventORM(
        event_id=str(event.event_id),
        problem_id=(
            str(event.top_match_problem_id)
            if event.top_match_problem_id is not None
            else None
        ),
        agent_id=str(event.agent_id) if event.agent_id is not None else None,
        query_text=event.query_text,
        ip_hash=event.ip_hash,
        fingerprint_hash=event.fingerprint_hash,
        top_match_quality=event.top_match_quality,
        has_help=event.has_help,
        is_self_hit=event.is_self_hit,
        is_seed_replay=event.is_seed_replay,
        is_seeded_hit=event.is_seeded_hit,
        pattern_class_hit=event.pattern_class_hit,
        created_at=event.created_at,
    )


class SQLAlchemyQueryEventRepository:
    """Persists query events; rollup math is delegated to the shared helper.

    The dedup window and exclusion rules mirror
    ``InMemoryQueryEventRepository`` exactly so both backends report
    identical recurrence metrics. Aggregation never reimplements the math:
    ``recurrence_rollup`` loads the rows and hands them to
    ``backend.application._recurrence.compute_recurrence_rollup``.
    """

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def add(self, event: QueryEvent) -> None:
        with self._session_factory() as session:
            session.add(_orm_from_query_event(event))
            session.commit()

    def add_with_dedup(
        self,
        event: QueryEvent,
        agents: AgentRepository,
        *,
        exclude_seed_replay: bool = True,
        exclude_self_hits: bool = True,
        dedup_window_seconds: int = 600,
    ) -> bool:
        if exclude_seed_replay and event.is_seed_replay:
            return False
        if exclude_self_hits and event.is_self_hit:
            return False

        window = timedelta(seconds=dedup_window_seconds)
        with self._session_factory() as session:
            problem_id = (
                str(event.top_match_problem_id)
                if event.top_match_problem_id is not None
                else None
            )
            stmt = select(QueryEventORM).where(
                QueryEventORM.created_at >= event.created_at - window,
                QueryEventORM.created_at <= event.created_at + window,
            )
            if problem_id is None:
                stmt = stmt.where(QueryEventORM.problem_id.is_(None))
            else:
                stmt = stmt.where(QueryEventORM.problem_id == problem_id)
            candidates = session.execute(stmt).scalars().all()
            for existing in candidates:
                if self._same_identity(_to_query_event_domain(existing), event, agents):
                    return False

            session.add(_orm_from_query_event(event))
            session.commit()
        return True

    def _same_identity(
        self, a: QueryEvent, b: QueryEvent, agents: AgentRepository
    ) -> bool:
        if a.agent_id is not None and b.agent_id is not None:
            if a.agent_id == b.agent_id:
                return True
            agent_a = agents.get(a.agent_id)
            agent_b = agents.get(b.agent_id)
            if agent_a is None or agent_b is None:
                return False
            for cluster in detect_clusters([agent_a, agent_b]):
                if a.agent_id in cluster and b.agent_id in cluster:
                    return True
            return False
        # At least one anonymous caller — match on shared identity hashes.
        if a.ip_hash and b.ip_hash and a.ip_hash == b.ip_hash:
            return True
        if (
            a.fingerprint_hash
            and b.fingerprint_hash
            and a.fingerprint_hash == b.fingerprint_hash
        ):
            return True
        return False

    def list_all(self, since: datetime | None = None) -> list[QueryEvent]:
        with self._session_factory() as session:
            stmt = select(QueryEventORM)
            if since is not None:
                stmt = stmt.where(QueryEventORM.created_at >= since)
            stmt = stmt.order_by(QueryEventORM.created_at.asc())
            rows = session.execute(stmt).scalars().all()
            return [_to_query_event_domain(r) for r in rows]

    def query_count_for_problem(
        self, problem_id: UUID, since: datetime | None = None
    ) -> int:
        with self._session_factory() as session:
            stmt = (
                select(func.count())
                .select_from(QueryEventORM)
                .where(QueryEventORM.problem_id == str(problem_id))
                .where(QueryEventORM.is_seed_replay.is_(False))
                .where(QueryEventORM.is_self_hit.is_(False))
            )
            if since is not None:
                stmt = stmt.where(QueryEventORM.created_at >= since)
            return session.execute(stmt).scalar_one()

    def recurrence_rollup(
        self,
        *,
        seed_agent_ids: frozenset[UUID] = frozenset(),
        since: datetime | None = None,
    ) -> dict:
        # ``since`` pushes a WHERE created_at >= since into list_all's SQL, so the
        # rollup never loads the full append-only history into memory.
        return compute_recurrence_rollup(
            self.list_all(since=since), seed_agent_ids=seed_agent_ids
        )
