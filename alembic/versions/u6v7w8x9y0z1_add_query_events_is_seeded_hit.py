"""add is_seeded_hit to query_events

Revision ID: u6v7w8x9y0z1
Revises: t5u6v7w8x9y0
Create Date: 2026-06-05 12:00:00.000000

Adds the ``is_seeded_hit`` flag to ``query_events``: whether the *matched
contributor* (the reliance target's author) is a seed/operator agent. The
recurrence rollup excludes seeded hits from ``organic_recurrence`` so a real
agent hitting a seeded entry counts as bootstrap value, not a peer-network
effect. Without this flag the organic signal cannot be separated from seeded
hits once a corpus is seeded (the instrument-before-seed guarantee).

``server_default="0"`` backfills existing rows as non-seeded; correct, since the
only pre-existing seed identity (SANDBOX_AGENT_ID) authored no real reliance
targets before this column existed.

Idempotent: skips when the column already exists so it is safe on both upgraded
prod DBs and fresh ORM-created installs.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "u6v7w8x9y0z1"
down_revision = "t5u6v7w8x9y0"
branch_labels = None
depends_on = None


def _column_exists(bind: sa.engine.Connection, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return any(col["name"] == column for col in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    if _column_exists(bind, "query_events", "is_seeded_hit"):
        return
    op.add_column(
        "query_events",
        sa.Column(
            "is_seeded_hit",
            sa.Boolean(),
            server_default="0",
            nullable=False,
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _column_exists(bind, "query_events", "is_seeded_hit"):
        return
    op.drop_column("query_events", "is_seeded_hit")
