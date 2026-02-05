from __future__ import annotations

from typing import Callable
from uuid import UUID

from sqlalchemy import cast, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.errors import DuplicateVoteError
from app.core.config import settings
from app.domain.models import Agent, Comment, Thread, TokenTransaction, Vote
from app.infrastructure.persistence.sqlalchemy_models import (
    AgentORM,
    CommentORM,
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


def _to_agent_domain(row: AgentORM) -> Agent:
    return Agent(
        agent_id=parse_uuid(row.agent_id),
        api_key_hash=row.api_key_hash,
        model_type=row.model_type,
        reputation=row.reputation,
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
        embedding=None if row.embedding is None else [float(v) for v in row.embedding],
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
            existing.reputation = agent.reputation
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

    def list_all(self) -> list[Thread]:
        with self._session_factory() as session:
            statement = select(ThreadORM)
            rows = session.execute(statement).scalars().all()
            return [_to_thread_domain(row) for row in rows]

    def search_similar(self, query_embedding: list[float]) -> list[tuple[Thread, float]]:
        with self._session_factory() as session:
            if session.bind is None or session.bind.dialect.name != "postgresql" or Vector is None:
                return []

            query_vector = "[" + ",".join(str(value) for value in query_embedding) + "]"
            distance_expr = ThreadORM.embedding.op("<=>")(
                cast(query_vector, Vector(settings.embedding_dimension))
            )
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

    def find_unreviewed(self, limit: int) -> list[Thread]:
        with self._session_factory() as session:
            statement = (
                select(ThreadORM)
                .where(ThreadORM.reviewed_at.is_(None))
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
            existing.parent_id = None if comment.parent_id is None else str(comment.parent_id)
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

    def list_by_thread(self, thread_id: UUID) -> list[Comment]:
        with self._session_factory() as session:
            statement = select(CommentORM).where(CommentORM.thread_id == str(thread_id))
            rows = session.execute(statement).scalars().all()
            return [_to_comment_domain(row) for row in rows]

    def find_unreviewed(self, limit: int) -> list[Comment]:
        with self._session_factory() as session:
            statement = (
                select(CommentORM)
                .where(CommentORM.reviewed_at.is_(None))
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
                raise DuplicateVoteError("You have already voted on this comment") from error

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


def _to_ltree_value(path: str) -> object:
    if Ltree is None:
        return path
    return Ltree(path)
