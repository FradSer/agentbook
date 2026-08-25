"""add failed_attempts to solutions and outcomes

Revision ID: v7w8x9y9z0a2
Revises: u6v7w8x9y0z1
Create Date: 2026-08-24 12:00:00.000000

Adds the negative half of the trajectory (trace + telemetry alignment):

- ``solutions.failed_attempts`` — authored dead ends: what did NOT work
  before this solution was found.
- ``outcomes.failed_attempts`` — reporter telemetry on failure reports:
  what the reporter tried before declaring the outcome.

Both are nullable JSON arrays of strings, optional so legacy rows remain
valid. They are published verbatim on public read paths and therefore
secret-gated at write time and scrubbed by the takedown path; they do NOT
feed the confidence math (policy v6 stays frozen).

Idempotent: skips when a column already exists so it is safe on both
upgraded prod DBs and fresh ORM-created installs.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "v7w8x9y9z0a2"
down_revision = "u6v7w8x9y0z1"
branch_labels = None
depends_on = None


def _column_exists(bind: sa.engine.Connection, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return False
    return any(col["name"] == column for col in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    json_type = sa.JSON().with_variant(JSONB(), "postgresql")
    for table in ("solutions", "outcomes"):
        if _column_exists(bind, table, "failed_attempts"):
            continue
        op.add_column(table, sa.Column("failed_attempts", json_type, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("solutions", "outcomes"):
        if not _column_exists(bind, table, "failed_attempts"):
            continue
        op.drop_column(table, "failed_attempts")
