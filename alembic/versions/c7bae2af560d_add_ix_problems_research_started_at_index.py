"""add ix_problems_research_started_at partial index

Revision ID: c7bae2af560d
Revises: l5e6f7a8b9c0
Create Date: 2026-05-01 14:53:34.990856

Partial index supporting per-connection SSE polling for the Live Research
Banner. The partial predicate keeps it small because research_started_at
is mostly NULL.

Pre-pilot scale uses plain ``CREATE INDEX`` rather than ``CREATE INDEX
CONCURRENTLY``. ``CONCURRENTLY`` cannot run inside the implicit psycopg2
transaction Alembic opens per migration, and at sub-1k-row volumes the
write-blocking window during a non-concurrent build is microseconds.
Revisit when corpus scale makes the blocking matter (move index creation
out of the migration, or switch the connection to AUTOCOMMIT for the
duration of this script).
"""

from __future__ import annotations

from alembic import op

revision = "c7bae2af560d"
down_revision = "l5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS "
        "ix_problems_research_started_at "
        "ON problems (research_started_at) "
        "WHERE research_started_at IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_problems_research_started_at")
