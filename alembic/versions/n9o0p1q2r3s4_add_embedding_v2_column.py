"""add embedding_v2 column with HNSW index for Voyage v3-large

Revision ID: n9o0p1q2r3s4
Revises: c7bae2af560d
Create Date: 2026-05-05 09:00:00.000000

Phase 3a of the false-positive fix migration. Adds a 1024-dim ``embedding_v2``
column alongside the legacy ``embedding`` column so the corpus can be
re-embedded with Voyage v3-large without downtime. ``embedding_version`` in
settings stays at ``v1`` (reads/writes still target ``embedding``) until
``backend/scripts/reembed_corpus.py`` backfills ``embedding_v2`` for all
rows; the operator then flips ``EMBEDDING_VERSION=v2`` to switch reads.

HNSW chosen over IVFFlat because pgvector >= 0.5 is GA, HNSW has better
recall/latency tradeoffs at agentbook's scale (thousands to millions of
rows), and the index rebuilds free on the empty column.

Rollback note: HNSW does not have the IVFFlat ``CREATE INDEX CONCURRENTLY``
INVALID-on-interrupt trap (HNSW indexes either complete or roll back), but
the column add is reversible. ``downgrade`` drops both index and column.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "n9o0p1q2r3s4"
down_revision = "c7bae2af560d"
branch_labels = None
depends_on = None


def _has_vector_extension() -> bool:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return False
    result = bind.execute(
        sa.text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
    ).scalar()
    return bool(result)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("problems")}

    # Idempotent column add — skip if a previous interrupted run already
    # added it. The vector type fall through is needed for the case where
    # pgvector isn't installed (Railway PG without the extension); the JSON
    # variant is forward-compatible thanks to FlexibleVector's TypeDecorator.
    if "embedding_v2" not in columns:
        if bind.dialect.name == "postgresql" and _has_vector_extension():
            op.execute("ALTER TABLE problems ADD COLUMN embedding_v2 vector(1024)")
        else:
            op.add_column(
                "problems",
                sa.Column("embedding_v2", sa.JSON(), nullable=True),
            )

    if bind.dialect.name == "postgresql" and _has_vector_extension():
        # Plain ``CREATE INDEX`` rather than ``CONCURRENTLY``: at pre-pilot
        # scale the column is empty until ``backend/scripts/reembed_corpus.py``
        # runs, so blocking is irrelevant. ``CONCURRENTLY`` also cannot run
        # inside the implicit transaction Alembic opens per migration.
        op.execute(
            "CREATE INDEX IF NOT EXISTS "
            "ix_problems_embedding_v2 "
            "ON problems USING hnsw (embedding_v2 vector_cosine_ops)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_problems_embedding_v2")

    inspector = inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("problems")}
    if "embedding_v2" in columns:
        op.drop_column("problems", "embedding_v2")
