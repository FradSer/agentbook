"""add problems.description tsvector GIN index for hybrid search

Revision ID: h1a2b3c4d5e6
Revises: g1h2i3j4k5l6
Create Date: 2026-04-15 07:30:00.000000

"""

from __future__ import annotations

from alembic import op

revision = "h1a2b3c4d5e6"
down_revision = "c6dadb0fd799"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add a GIN index on `to_tsvector('english', description)`.

    Used by `SQLAlchemyProblemRepository.find_hybrid` for the sparse
    (lexical) leg of hybrid retrieval. Built `CONCURRENTLY` so the
    migration does not lock writers; that requires running outside a
    transaction.

    The index is best-effort — if the bind is not PostgreSQL the migration
    is a no-op so non-PG dev environments stay green.
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "ix_problems_description_tsv "
            "ON problems USING GIN (to_tsvector('english', description))"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_problems_description_tsv")
