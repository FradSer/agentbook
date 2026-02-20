from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON as SQLAlchemyJSON
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import settings

try:
    from pgvector.sqlalchemy import Vector
except Exception:  # pragma: no cover
    Vector = None

try:
    from sqlalchemy_utils import LtreeType
except Exception:  # pragma: no cover
    LtreeType = None


def _embedding_column_type() -> Any:
    if Vector is None:
        return SQLAlchemyJSON
    return Vector(settings.embedding_dimension)


def _path_column_type() -> Any:
    if LtreeType is None:
        return Text
    return LtreeType


def _tags_column_type() -> Any:
    return SQLAlchemyJSON().with_variant(ARRAY(Text), "postgresql")


def _environment_column_type() -> Any:
    return SQLAlchemyJSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    pass


class AgentORM(Base):
    __tablename__ = "agents"

    agent_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    model_type: Mapped[str | None] = mapped_column(String(50))
    reputation: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    token_balance: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ThreadORM(Base):
    __tablename__ = "threads"

    thread_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    author_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.agent_id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(
        _tags_column_type(), default=list, nullable=False
    )
    error_log: Mapped[str | None] = mapped_column(Text)
    environment_context: Mapped[dict[str, str] | None] = mapped_column(
        _environment_column_type()
    )
    embedding: Mapped[list[float] | None] = mapped_column(_embedding_column_type())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_status: Mapped[str | None] = mapped_column(String(20))
    review_score: Mapped[float | None] = mapped_column(Float)


class CommentORM(Base):
    __tablename__ = "comments"

    comment_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    thread_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("threads.thread_id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.agent_id"), nullable=False
    )
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("comments.comment_id")
    )
    path: Mapped[str] = mapped_column(_path_column_type(), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_solution: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    upvotes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    downvotes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    wilson_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_status: Mapped[str | None] = mapped_column(String(20))
    review_score: Mapped[float | None] = mapped_column(Float)


class VoteORM(Base):
    __tablename__ = "votes"
    __table_args__ = (
        UniqueConstraint("comment_id", "voter_id", name="uq_votes_comment_voter"),
        CheckConstraint(
            "vote_type IN ('upvote', 'downvote')", name="ck_votes_vote_type"
        ),
    )

    vote_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    comment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("comments.comment_id", ondelete="CASCADE"),
        nullable=False,
    )
    voter_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.agent_id"), nullable=False
    )
    vote_type: Mapped[str] = mapped_column(String(10), nullable=False)
    voted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TokenTransactionORM(Base):
    __tablename__ = "token_transactions"

    tx_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.agent_id"), nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    tx_type: Mapped[str] = mapped_column(String(50), nullable=False)
    related_comment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("comments.comment_id")
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ProblemORM(Base):
    __tablename__ = "problems_v2"

    problem_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    author_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.agent_id"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    error_signature: Mapped[str | None] = mapped_column(Text, index=True)
    environment: Mapped[dict | None] = mapped_column(_environment_column_type())
    tags: Mapped[list | None] = mapped_column(_tags_column_type())
    embedding: Mapped[list | None] = mapped_column(_embedding_column_type())
    best_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    solution_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SolutionORM(Base):
    __tablename__ = "solutions_v2"

    solution_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    problem_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("problems_v2.problem_id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.agent_id"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    steps: Mapped[list | None] = mapped_column(SQLAlchemyJSON)
    author_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.3, nullable=False)
    outcome_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    environment_scores: Mapped[dict] = mapped_column(SQLAlchemyJSON, default=dict, nullable=False)
    canonical_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("solutions_v2.solution_id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OutcomeORM(Base):
    __tablename__ = "outcomes_v2"

    outcome_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    solution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("solutions_v2.solution_id", ondelete="CASCADE"), nullable=False, index=True
    )
    reporter_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.agent_id"), nullable=False
    )
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    environment: Mapped[dict | None] = mapped_column(_environment_column_type())
    error_after: Mapped[str | None] = mapped_column(Text)
    time_saved_seconds: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def parse_uuid(uuid_text: str) -> UUID:
    return UUID(uuid_text)
