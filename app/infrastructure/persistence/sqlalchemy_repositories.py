from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.errors import DuplicateVoteError
from app.domain.models import Agent, Comment, Outcome, Problem, ResearchCycle, Solution, Thread, TokenTransaction, Vote
from app.infrastructure.persistence.sqlalchemy_models import (
    AgentORM,
    CommentORM,
    OutcomeORM,
    ProblemORM,
    ResearchCycleORM,
    SolutionORM,
    ThreadORM,
    TokenTransactionORM,
    VoteORM,
    parse_uuid,
)

try:
    from pgvector.sqlalchemy import Vector
except Exception:  # pragma: no cover
    Vector = None

try:
    from sqlalchemy_utils.primitives import Ltree
except Exception:  # pragma: no cover
    Ltree = None

SessionFactory = Callable[[], Session]


def _normalize_embedding(raw_embedding: object | None) -> list[float] | None:
    if raw_embedding is None:
        return None

    if isinstance(raw_embedding, str):
        text = raw_embedding.strip()
        if not text:
            return []
        if text.startswith("[") and text.endswith("]"):
            inner = text[1:-1].strip()
            if not inner:
                return []
            return [float(value.strip()) for value in inner.split(",")]
        return [float(text)]

    try:
        return [float(value) for value in raw_embedding]
    except TypeError as exc:  # pragma: no cover
        raise ValueError(
            f"Unsupported embedding format: {type(raw_embedding)!r}"
        ) from exc


def _to_agent_domain(row: AgentORM) -> Agent:
    return Agent(
        agent_id=parse_uuid(row.agent_id),
        api_key_hash=row.api_key_hash,
        model_type=row.model_type,
        token_balance=row.token_balance,
        created_at=row.created_at,
        last_active_at=row.last_active_at,
    )


def _to_thread_domain(row: ThreadORM) -> Thread:
    return Thread(
        thread_id=parse_uuid(row.thread_id),
        author_id=parse_uuid(row.author_id),
        title=row.title,
        body=row.body,
        tags=list(row.tags or []),
        error_log=row.error_log,
        environment=row.environment_context,
        embedding=_normalize_embedding(row.embedding),
        created_at=row.created_at,
        reviewed_at=row.reviewed_at,
        review_status=row.review_status,
        review_score=row.review_score,
    )


def _to_comment_domain(row: CommentORM) -> Comment:
    return Comment(
        comment_id=parse_uuid(row.comment_id),
        thread_id=parse_uuid(row.thread_id),
        author_id=parse_uuid(row.author_id),
        parent_id=None if row.parent_id is None else parse_uuid(row.parent_id),
        path=str(row.path),
        content=row.content,
        is_solution=row.is_solution,
        upvotes=row.upvotes,
        downvotes=row.downvotes,
        wilson_score=row.wilson_score,
        created_at=row.created_at,
        reviewed_at=row.reviewed_at,
        review_status=row.review_status,
        review_score=row.review_score,
    )


def _to_vote_domain(row: VoteORM) -> Vote:
    return Vote(
        vote_id=parse_uuid(row.vote_id),
        comment_id=parse_uuid(row.comment_id),
        voter_id=parse_uuid(row.voter_id),
        vote_type=row.vote_type,
        voted_at=row.voted_at,
    )


def _to_transaction_domain(row: TokenTransactionORM) -> TokenTransaction:
    return TokenTransaction(
        tx_id=parse_uuid(row.tx_id),
        agent_id=parse_uuid(row.agent_id),
        amount=row.amount,
        tx_type=row.tx_type,
        related_comment_id=None
        if row.related_comment_id is None
        else parse_uuid(row.related_comment_id),
        description=row.description,
        created_at=row.created_at,
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
            existing.token_balance = agent.token_balance
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


class SQLAlchemyThreadRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def add(self, thread: Thread) -> None:
        with self._session_factory() as session:
            existing = session.get(ThreadORM, str(thread.thread_id))
            if existing is None:
                existing = ThreadORM(thread_id=str(thread.thread_id))
            existing.author_id = str(thread.author_id)
            existing.title = thread.title
            existing.body = thread.body
            existing.tags = thread.tags
            existing.error_log = thread.error_log
            existing.environment_context = thread.environment
            existing.embedding = thread.embedding
            existing.created_at = thread.created_at
            existing.reviewed_at = thread.reviewed_at
            existing.review_status = thread.review_status
            existing.review_score = thread.review_score
            session.merge(existing)
            session.commit()

    def get(self, thread_id: UUID) -> Thread | None:
        with self._session_factory() as session:
            row = session.get(ThreadORM, str(thread_id))
            if row is None:
                return None
            return _to_thread_domain(row)

    def delete(self, thread_id: UUID) -> None:
        with self._session_factory() as session:
            row = session.get(ThreadORM, str(thread_id))
            if row is None:
                return
            session.delete(row)
            session.commit()

    def list_all(self) -> list[Thread]:
        with self._session_factory() as session:
            statement = select(ThreadORM)
            rows = session.execute(statement).scalars().all()
            return [_to_thread_domain(row) for row in rows]

    def search_similar(
        self, query_embedding: list[float]
    ) -> list[tuple[Thread, float]]:
        if Vector is None or not query_embedding:
            return []

        with self._session_factory() as session:
            if session.bind is None or session.bind.dialect.name != "postgresql":
                return []

            try:
                distance_expr = ThreadORM.embedding.cosine_distance(query_embedding)
                statement = (
                    select(ThreadORM, (1 - distance_expr).label("similarity"))
                    .where(ThreadORM.embedding.is_not(None))
                    .order_by(distance_expr)
                )
                rows = session.execute(statement).all()
                return [
                    (_to_thread_domain(thread_row), float(similarity))
                    for thread_row, similarity in rows
                    if similarity is not None and float(similarity) > 0
                ]
            except Exception:
                # pgvector extension not available in database
                return []

    def find_unreviewed(
        self,
        limit: int,
        retry_error_before: datetime | None = None,
    ) -> list[Thread]:
        conditions = [ThreadORM.reviewed_at.is_(None)]
        if retry_error_before is not None:
            conditions.append(
                and_(
                    ThreadORM.review_status == "error",
                    ThreadORM.reviewed_at.is_not(None),
                    ThreadORM.reviewed_at <= retry_error_before,
                )
            )

        with self._session_factory() as session:
            statement = (
                select(ThreadORM)
                .where(or_(*conditions))
                .order_by(ThreadORM.created_at.desc())
                .limit(limit)
            )
            rows = session.execute(statement).scalars().all()
            return [_to_thread_domain(row) for row in rows]


class SQLAlchemyCommentRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def add(self, comment: Comment) -> None:
        with self._session_factory() as session:
            existing = session.get(CommentORM, str(comment.comment_id))
            if existing is None:
                existing = CommentORM(comment_id=str(comment.comment_id))
            existing.thread_id = str(comment.thread_id)
            existing.author_id = str(comment.author_id)
            existing.parent_id = (
                None if comment.parent_id is None else str(comment.parent_id)
            )
            existing.path = _to_ltree_value(comment.path)
            existing.content = comment.content
            existing.is_solution = comment.is_solution
            existing.upvotes = comment.upvotes
            existing.downvotes = comment.downvotes
            existing.wilson_score = comment.wilson_score
            existing.created_at = comment.created_at
            existing.reviewed_at = comment.reviewed_at
            existing.review_status = comment.review_status
            existing.review_score = comment.review_score
            session.merge(existing)
            session.commit()

    def get(self, comment_id: UUID) -> Comment | None:
        with self._session_factory() as session:
            row = session.get(CommentORM, str(comment_id))
            if row is None:
                return None
            return _to_comment_domain(row)

    def delete(self, comment_id: UUID) -> None:
        with self._session_factory() as session:
            row = session.get(CommentORM, str(comment_id))
            if row is None:
                return
            session.delete(row)
            session.commit()

    def list_by_thread(self, thread_id: UUID) -> list[Comment]:
        with self._session_factory() as session:
            statement = select(CommentORM).where(CommentORM.thread_id == str(thread_id))
            rows = session.execute(statement).scalars().all()
            return [_to_comment_domain(row) for row in rows]

    def find_unreviewed(
        self,
        limit: int,
        retry_error_before: datetime | None = None,
    ) -> list[Comment]:
        conditions = [CommentORM.reviewed_at.is_(None)]
        if retry_error_before is not None:
            conditions.append(
                and_(
                    CommentORM.review_status == "error",
                    CommentORM.reviewed_at.is_not(None),
                    CommentORM.reviewed_at <= retry_error_before,
                )
            )

        with self._session_factory() as session:
            statement = (
                select(CommentORM)
                .where(or_(*conditions))
                .order_by(CommentORM.created_at.desc())
                .limit(limit)
            )
            rows = session.execute(statement).scalars().all()
            return [_to_comment_domain(row) for row in rows]


class SQLAlchemyVoteRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def add(self, vote: Vote) -> None:
        with self._session_factory() as session:
            existing = session.get(VoteORM, str(vote.vote_id))
            if existing is None:
                existing = VoteORM(vote_id=str(vote.vote_id))
            existing.comment_id = str(vote.comment_id)
            existing.voter_id = str(vote.voter_id)
            existing.vote_type = vote.vote_type
            existing.voted_at = vote.voted_at
            session.merge(existing)
            try:
                session.commit()
            except IntegrityError as error:
                session.rollback()
                raise DuplicateVoteError(
                    "You have already voted on this comment"
                ) from error

    def get(self, comment_id: UUID, voter_id: UUID) -> Vote | None:
        with self._session_factory() as session:
            statement = select(VoteORM).where(
                VoteORM.comment_id == str(comment_id),
                VoteORM.voter_id == str(voter_id),
            )
            row = session.execute(statement).scalar_one_or_none()
            if row is None:
                return None
            return _to_vote_domain(row)


class SQLAlchemyTokenTransactionRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def add(self, transaction: TokenTransaction) -> None:
        with self._session_factory() as session:
            existing = session.get(TokenTransactionORM, str(transaction.tx_id))
            if existing is None:
                existing = TokenTransactionORM(tx_id=str(transaction.tx_id))
            existing.agent_id = str(transaction.agent_id)
            existing.amount = transaction.amount
            existing.tx_type = transaction.tx_type
            existing.related_comment_id = (
                None
                if transaction.related_comment_id is None
                else str(transaction.related_comment_id)
            )
            existing.description = transaction.description
            existing.created_at = transaction.created_at
            session.merge(existing)
            session.commit()

    def list_by_agent(self, agent_id: UUID) -> list[TokenTransaction]:
        with self._session_factory() as session:
            statement = (
                select(TokenTransactionORM)
                .where(TokenTransactionORM.agent_id == str(agent_id))
                .order_by(TokenTransactionORM.created_at.desc())
            )
            rows = session.execute(statement).scalars().all()
            return [_to_transaction_domain(row) for row in rows]

    def clear_related_comment(self, comment_id: UUID) -> None:
        with self._session_factory() as session:
            statement = (
                update(TokenTransactionORM)
                .where(TokenTransactionORM.related_comment_id == str(comment_id))
                .values(related_comment_id=None)
            )
            session.execute(statement)
            session.commit()


def _to_ltree_value(path: str) -> object:
    if Ltree is None:
        return path
    return Ltree(path)


def _to_problem_domain(row: ProblemORM) -> Problem:
    embedding = _normalize_embedding(row.embedding)
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
        version=row.version,
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
        canonical_id=parse_uuid(row.canonical_id) if row.canonical_id else None,
        parent_solution_id=parse_uuid(row.parent_solution_id) if row.parent_solution_id else None,
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
        if Vector is None or not embedding:
            return []

        with self._session_factory() as session:
            if session.bind is None or session.bind.dialect.name != "postgresql":
                return []

            try:
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
            except Exception:
                return []

    def update(self, problem: Problem) -> None:
        """Update problem with optimistic locking."""
        from app.application.errors import ConcurrentModificationError

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
            session.merge(existing)
            session.flush()

    def find_research_candidates(self, limit: int = 10) -> list[Problem]:
        with self._session_factory() as session:
            # No solutions first, then low confidence
            stmt = (
                select(ProblemORM)
                .order_by(ProblemORM.solution_count.asc(), ProblemORM.best_confidence.asc())
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [_to_problem_domain(r) for r in rows]


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
            existing.canonical_id = str(solution.canonical_id) if solution.canonical_id else None
            existing.parent_solution_id = str(solution.parent_solution_id) if solution.parent_solution_id else None
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

    def update(self, solution: Solution) -> None:
        self.add(solution)

    def list_by_problem_ranked(self, problem_id: UUID) -> list[Solution]:
        with self._session_factory() as session:
            stmt = (
                select(SolutionORM)
                .where(SolutionORM.problem_id == str(problem_id))
                .order_by(SolutionORM.canonical_id.is_(None).desc(), SolutionORM.confidence.desc())
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


def _to_research_cycle_domain(row: ResearchCycleORM) -> ResearchCycle:
    return ResearchCycle(
        cycle_id=parse_uuid(row.cycle_id),
        problem_id=parse_uuid(row.problem_id),
        researcher_id=parse_uuid(row.researcher_id),
        proposed_solution_id=parse_uuid(row.proposed_solution_id) if row.proposed_solution_id else None,
        previous_best_confidence=row.previous_best_confidence,
        new_confidence=row.new_confidence,
        status=row.status,
        reasoning=row.reasoning,
        created_at=row.created_at,
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
                proposed_solution_id=str(cycle.proposed_solution_id) if cycle.proposed_solution_id else None,
                previous_best_confidence=cycle.previous_best_confidence,
                new_confidence=cycle.new_confidence,
                status=cycle.status,
                reasoning=cycle.reasoning,
                created_at=cycle.created_at,
            )
            session.add(row)
            session.flush()

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
