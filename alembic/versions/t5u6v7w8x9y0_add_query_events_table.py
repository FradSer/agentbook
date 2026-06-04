"""add query_events table

Revision ID: t5u6v7w8x9y0
Revises: s4t5u6v7w8x9
Create Date: 2026-06-04 12:00:00.000000

Adds the append-only ``query_events`` table backing the recurrence-density
instrument. Each row records a cache-miss search: the matched problem (FK to
``problems`` with ``ON DELETE CASCADE``, nullable), the caller (FK to
``agents``, nullable for anonymous traffic), identity hashes, and the match
quality / exclusion flags the rollup math reads. No unique constraint — the
table is append-only and dedup happens at the repository layer. No embedding
column.

Idempotent: skips table creation when ``query_events`` already exists so it is
safe on both upgraded prod DBs and fresh ORM-created installs.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "t5u6v7w8x9y0"
down_revision = "s4t5u6v7w8x9"
branch_labels = None
depends_on = None


def _table_exists(bind: sa.engine.Connection, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    if _table_exists(op.get_bind(), "query_events"):
        return
    op.create_table(
        "query_events",
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("problem_id", sa.String(length=36), nullable=True),
        sa.Column("agent_id", sa.String(length=36), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("fingerprint_hash", sa.String(length=64), nullable=True),
        sa.Column("top_match_quality", sa.String(length=10), nullable=True),
        sa.Column("has_help", sa.Boolean(), nullable=False),
        sa.Column("is_self_hit", sa.Boolean(), nullable=False),
        sa.Column("is_seed_replay", sa.Boolean(), nullable=False),
        sa.Column(
            "pattern_class_hit",
            sa.Boolean(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["problem_id"],
            ["problems.problem_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.agent_id"]),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("ix_query_events_problem_id", "query_events", ["problem_id"])
    op.create_index("ix_query_events_agent_id", "query_events", ["agent_id"])
    op.create_index("ix_query_events_created_at", "query_events", ["created_at"])


def downgrade() -> None:
    if not _table_exists(op.get_bind(), "query_events"):
        return
    op.drop_index("ix_query_events_created_at", table_name="query_events")
    op.drop_index("ix_query_events_agent_id", table_name="query_events")
    op.drop_index("ix_query_events_problem_id", table_name="query_events")
    op.drop_table("query_events")
