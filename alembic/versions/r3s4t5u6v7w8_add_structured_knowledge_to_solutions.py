"""add structured knowledge fields to solutions

Revision ID: r3s4t5u6v7w8
Revises: q2r3s4t5u6v7
Create Date: 2026-06-01 00:00:00.000000

Adds the weak-model-actionable knowledge fields to ``solutions`` —
``root_cause_pattern`` (TEXT), ``localization_cues`` (JSON), and
``verification`` (JSON). This is the structured, verifiable form that the
agentbook-ab attribution run showed drives the consumer lift (root-cause
pattern + where-to-look cues + runnable repros). All three are nullable so
every existing row stays valid and legacy/minimal solutions remain creatable.

Idempotent: skips any column that already exists (e.g. when the ORM created
the table fresh with these columns), so it is safe on both upgraded prod DBs
and fresh installs.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "r3s4t5u6v7w8"
down_revision = "q2r3s4t5u6v7"
branch_labels = None
depends_on = None

_COLUMNS: dict[str, sa.types.TypeEngine] = {
    "root_cause_pattern": sa.Text(),
    "localization_cues": sa.JSON(),
    "verification": sa.JSON(),
}


def _existing_columns(bind: sa.engine.Connection) -> set[str]:
    return {col["name"] for col in sa.inspect(bind).get_columns("solutions")}


def upgrade() -> None:
    existing = _existing_columns(op.get_bind())
    for name, type_ in _COLUMNS.items():
        if name not in existing:
            op.add_column("solutions", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    existing = _existing_columns(op.get_bind())
    for name in _COLUMNS:
        if name in existing:
            op.drop_column("solutions", name)
