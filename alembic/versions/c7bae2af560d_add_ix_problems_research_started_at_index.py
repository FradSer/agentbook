"""add ix_problems_research_started_at partial index

Revision ID: c7bae2af560d
Revises: l5e6f7a8b9c0
Create Date: 2026-05-01 14:53:34.990856

This index supports per-connection SSE polling for the Live Research Banner.
The partial predicate keeps the index small because research_started_at is
mostly NULL.

Rollback note: CREATE INDEX CONCURRENTLY leaves an INVALID index if
interrupted (network drop, OOM, deploy abort). Before re-running:

    DROP INDEX IF EXISTS ix_problems_research_started_at;

This script's downgrade drops the index unconditionally, which also
cleans up an INVALID index left behind by an interrupted forward run.
"""

from __future__ import annotations

from alembic import op

revision = "c7bae2af560d"
down_revision = "l5e6f7a8b9c0"
branch_labels = None
depends_on = None

# Required so CONCURRENTLY runs outside a transaction.
disable_ddl_transaction = True


def upgrade() -> None:
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_problems_research_started_at "
        "ON problems (research_started_at) "
        "WHERE research_started_at IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_problems_research_started_at")
