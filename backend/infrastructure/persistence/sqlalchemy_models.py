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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from backend.core.config import settings

try:
    from pgvector.sqlalchemy import Vector
except Exception:  # pragma: no cover
    Vector = None


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

    def process_result_value(
        self, value: object, dialect: object
    ) -> list[float] | None:
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fingerprint_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


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
    # Voyage v3-large 1024-dim column added by the
    # ``add_embedding_v2_column`` Alembic migration. ``embedding_version=v2``
    # in settings flips reads to this column. Existing rows stay NULL until
    # ``backend/scripts/reembed_corpus.py`` backfills them; service-level
    # dual-write keeps new writes current.
    embedding_v2: Mapped[list | None] = mapped_column(FlexibleVector(1024))
    best_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    solution_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    review_status: Mapped[str | None] = mapped_column(String(20), index=True)
    review_score: Mapped[float | None] = mapped_column(Float)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canonical_solution_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("solutions.solution_id", use_alter=True), nullable=True
    )
    research_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )


class SolutionORM(Base):
    __tablename__ = "solutions"
    __table_args__ = (
        CheckConstraint("parent_solution_id != solution_id", name="ck_no_self_parent"),
    )

    solution_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    problem_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("problems.problem_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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
    llm_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    root_cause_pattern: Mapped[str | None] = mapped_column(Text, nullable=True)
    localization_cues: Mapped[list | None] = mapped_column(SQLAlchemyJSON)
    verification: Mapped[list | None] = mapped_column(SQLAlchemyJSON)
    root_cause_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class OutcomeORM(Base):
    __tablename__ = "outcomes"

    outcome_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    solution_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("solutions.solution_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reporter_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.agent_id"), nullable=False
    )
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    environment: Mapped[dict | None] = mapped_column(_environment_column_type())
    time_saved_seconds: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    error_after: Mapped[str | None] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    kind: Mapped[str] = mapped_column(
        String(10), server_default="observed", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Mirror of the Postgres-level CHECK constraint added by migration
    # ``2026_05_05_outcome_kind_not_null_with_check.py``. Declaring it
    # at the ORM level so SQLite-backed unit tests also reject forged
    # kind values and the constraint travels with the model definition.
    # ``uq_outcome_reporter_solution`` enforces v6's anti-inflation rule
    # at the database layer: the same reporter cannot vote twice on the
    # same solution. Installed by migration
    # ``p1q2r3s4t5u6_outcome_reporter_solution_unique`` and surfaced here
    # so SQLite-backed unit tests pick the same constraint up.
    __table_args__ = (
        CheckConstraint(
            "kind IN ('verified', 'observed')",
            name="outcomes_kind_check",
        ),
        UniqueConstraint(
            "solution_id",
            "reporter_id",
            name="uq_outcome_reporter_solution",
        ),
    )


class QueryEventORM(Base):
    __tablename__ = "query_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    problem_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("problems.problem_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    agent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("agents.agent_id"), nullable=True, index=True
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fingerprint_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    top_match_quality: Mapped[str | None] = mapped_column(String(10), nullable=True)
    has_help: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_self_hit: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_seed_replay: Mapped[bool] = mapped_column(Boolean, nullable=False)
    pattern_class_hit: Mapped[bool] = mapped_column(
        Boolean, server_default="0", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


def parse_uuid(uuid_text: str) -> UUID:
    return UUID(uuid_text)


class ResearchCycleORM(Base):
    __tablename__ = "research_cycles"

    cycle_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    problem_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("problems.problem_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    researcher_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.agent_id"), nullable=False
    )
    proposed_solution_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("solutions.solution_id")
    )
    previous_best_confidence: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    new_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, default="", nullable=False)
    llm_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
