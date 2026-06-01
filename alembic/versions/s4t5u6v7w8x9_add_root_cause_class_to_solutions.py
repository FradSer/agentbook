"""add root_cause_class to solutions

Revision ID: s4t5u6v7w8x9
Revises: r3s4t5u6v7w8
Create Date: 2026-06-01 12:00:00.000000

Adds ``root_cause_class`` (TEXT, nullable) to ``solutions`` — a discrete
root-cause class slug (e.g. ``identity-element-fallback``) the synthesis pass
emits and the service mirrors onto the problem as a ``pattern:<slug>`` tag so
cross-task retrieval can match a sibling by root cause when its surface text
differs. Validated at n=56 (cross-task retrieval 0% -> 55%); see
experiments/agentbook-ab/_report/04_cross_task_retrieval.md.

Idempotent: skips the column if it already exists, so it is safe on both
upgraded prod DBs and fresh ORM-created installs.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "s4t5u6v7w8x9"
down_revision = "r3s4t5u6v7w8"
branch_labels = None
depends_on = None


def _existing_columns(bind: sa.engine.Connection) -> set[str]:
    return {col["name"] for col in sa.inspect(bind).get_columns("solutions")}


def upgrade() -> None:
    if "root_cause_class" not in _existing_columns(op.get_bind()):
        op.add_column(
            "solutions", sa.Column("root_cause_class", sa.Text(), nullable=True)
        )


def downgrade() -> None:
    if "root_cause_class" in _existing_columns(op.get_bind()):
        op.drop_column("solutions", "root_cause_class")
