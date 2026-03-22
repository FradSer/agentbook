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
    TypeDecorator,
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


class FlexibleVector(TypeDecorator):
    """Embedding column that handles both pgvector string and JSON list storage.

    Uses JSON as the underlying impl so that psycopg2 returns a Python list
    directly, bypassing pgvector's result_processor (which crashes when the DB
    column is JSON instead of vector).  Handles string format too for forward
    compatibility when a true vector column is read without the type registered.
    """

    impl = SQLAlchemyJSON
    cache_ok = True

    def __init__(self, dim: int) -> None:
        self._dim = dim
        super().__init__()

    def process_result_value(self, value: object, dialect: object) -> list[float] | None:
        if value is None:
            return None
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            inner = value.strip("[] ")
            if not inner:
                return []
            return [float(v) for v in inner.split(",")]
        try:
            return [float(v) for v in value]  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    def process_bind_param(self, value: object, dialect: object) -> object:
        return value


def _embedding_column_type() -> Any:
    return FlexibleVector(settings.embedding_dimension)


def _path_column_type() -> Any:
    # Use Text as fallback when ltree Python package is unavailable.
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
    token_balance: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class TokenTransactionORM(Base):
    __tablename__ = "token_transactions"

    tx_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.agent_id"), nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    tx_type: Mapped[str] = mapped_column(String(50), nullable=False)
    related_solution_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("solutions.solution_id"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ProblemORM(Base):
    __tablename__ = "problems"

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
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    review_status: Mapped[str | None] = mapped_column(String(20), index=True)
    review_score: Mapped[float | None] = mapped_column(Float)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canonical_solution_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("solutions.solution_id", use_alter=True), nullable=True
    )
    research_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SolutionORM(Base):
    __tablename__ = "solutions"
    __table_args__ = (
        CheckConstraint("parent_solution_id != solution_id", name="ck_no_self_parent"),
    )

    solution_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    problem_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("problems.problem_id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.agent_id"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    steps: Mapped[list | None] = mapped_column(SQLAlchemyJSON)
    confidence: Mapped[float] = mapped_column(Float, default=0.3, nullable=False)
    outcome_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    canonical_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("solutions.solution_id")
    )
    parent_solution_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("solutions.solution_id")
    )
    promotion_status: Mapped[str | None] = mapped_column(String(20))
    review_status: Mapped[str | None] = mapped_column(String(20), index=True)
    review_score: Mapped[float | None] = mapped_column(Float)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    environment_scores: Mapped[dict] = mapped_column(SQLAlchemyJSON, default=dict, nullable=False)
    llm_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OutcomeORM(Base):
    __tablename__ = "outcomes"

    outcome_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    solution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("solutions.solution_id", ondelete="CASCADE"), nullable=False, index=True
    )
    reporter_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.agent_id"), nullable=False
    )
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    environment: Mapped[dict | None] = mapped_column(_environment_column_type())
    time_saved_seconds: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def parse_uuid(uuid_text: str) -> UUID:
    return UUID(uuid_text)


class ResearchCycleORM(Base):
    __tablename__ = "research_cycles"

    cycle_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    problem_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("problems.problem_id", ondelete="CASCADE"), nullable=False, index=True
    )
    researcher_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.agent_id"), nullable=False
    )
    proposed_solution_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("solutions.solution_id")
    )
    previous_best_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    new_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, default="", nullable=False)
    llm_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
