"""add applied_changes to outcomes

Revision ID: w8x9y9z0a1b3
Revises: v7w8x9y9z0a2
Create Date: 2026-08-26 12:00:00.000000

Edit-distance telemetry (trace + telemetry alignment, third level): what the
reporter CHANGED relative to the recalled solution before it worked.
Nullable JSON array of strings; optional so legacy rows remain valid.

Published verbatim on public read paths — secret-gated at write time and
scrubbed by the takedown path. Does NOT feed the confidence math (v6 frozen).

Idempotent: skips when the column already exists.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "w8x9y9z0a1b3"
down_revision = "v7w8x9y9z0a2"
branch_labels = None
depends_on = None


def _column_exists(bind: sa.engine.Connection, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return any(col["name"] == column for col in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    if _column_exists(bind, "outcomes", "applied_changes"):
        return
    json_type = sa.JSON().with_variant(JSONB(), "postgresql")
    op.add_column("outcomes", sa.Column("applied_changes", json_type, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if not _column_exists(bind, "outcomes", "applied_changes"):
        return
    op.drop_column("outcomes", "applied_changes")
