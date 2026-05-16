"""normalize embedding columns to json

Revision ID: q2r3s4t5u6v7
Revises: p1q2r3s4t5u6
Create Date: 2026-05-16 00:00:00.000000

Repairs databases where ``problems.embedding`` / ``problems.embedding_v2``
were created as pgvector ``vector`` columns by an earlier revision of the
``bdf1f1e79252`` / ``n9o0p1q2r3s4`` migrations. The ORM binds embeddings as
JSON lists via ``FlexibleVector``, so a ``vector`` column rejects every
``problems`` write with ``psycopg2.errors.DatatypeMismatch``. This migration
converts any surviving ``vector`` column to ``json`` and drops the now-unused
ivfflat / HNSW indexes.

It is a no-op on databases that already store the columns as JSON (Railway PG
without the extension, and fresh installs of the corrected migrations).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "q2r3s4t5u6v7"
down_revision = "p1q2r3s4t5u6"
branch_labels = None
depends_on = None

# ivfflat / HNSW indexes can only exist on a ``vector`` column.
_VECTOR_INDEXES = ("ix_problems_v2_embedding", "ix_problems_embedding_v2")


def _vector_columns(bind: sa.engine.Connection) -> set[str]:
    """Names of ``problems`` columns still typed as pgvector ``vector``."""
    rows = bind.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'problems' "
            "AND udt_name = 'vector'"
        )
    ).fetchall()
    return {row[0] for row in rows}


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    vector_cols = _vector_columns(bind)
    if not vector_cols:
        return

    # Drop the vector indexes before the type change so the ALTER does not
    # fail on an index dependency.
    for index_name in _VECTOR_INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {index_name}")

    # Preserve any stored embedding by casting vector -> real[] -> json;
    # NULL rows stay NULL.
    for column in sorted(vector_cols):
        op.execute(
            f"ALTER TABLE problems ALTER COLUMN {column} "
            f"TYPE json USING to_json({column}::real[])"
        )


def downgrade() -> None:
    # No-op: the JSON column type is the canonical representation on every
    # backend. Re-creating a pgvector column would reintroduce the write
    # incompatibility this migration exists to remove.
    pass
