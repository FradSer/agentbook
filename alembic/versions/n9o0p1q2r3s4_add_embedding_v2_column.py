"""add embedding_v2 column for Voyage v3-large

Revision ID: n9o0p1q2r3s4
Revises: c7bae2af560d
Create Date: 2026-05-05 09:00:00.000000

Phase 3a of the false-positive fix migration. Adds a 1024-dim ``embedding_v2``
column alongside the legacy ``embedding`` column so the corpus can be
re-embedded with Voyage v3-large without downtime. ``embedding_version`` in
settings stays at ``v1`` (reads/writes still target ``embedding``) until
``backend/scripts/reembed_corpus.py`` backfills ``embedding_v2`` for all
rows; the operator then flips ``EMBEDDING_VERSION=v2`` to switch reads.

``embedding_v2`` is created as plain ``JSON`` on every backend. A real
pgvector ``vector`` column is intentionally never created: the ORM binds
embeddings as JSON lists via ``FlexibleVector``, so a ``vector`` column would
reject every ``problems`` write with ``DatatypeMismatch``. The
``q2r3s4t5u6v7`` migration repairs any database that still has a legacy
``vector`` column from an earlier revision of this file.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "n9o0p1q2r3s4"
down_revision = "c7bae2af560d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("problems")}

    # Idempotent column add — skip if a previous interrupted run already
    # added it.
    if "embedding_v2" not in columns:
        op.add_column(
            "problems",
            sa.Column("embedding_v2", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("problems")}
    if "embedding_v2" in columns:
        op.drop_column("problems", "embedding_v2")
