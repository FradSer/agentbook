"""Unify V2 table names: remove _v2 suffix

Revision ID: d4e5f6a7b8c9
Revises: c3a1f7d82e94
Create Date: 2026-03-11

"""

from __future__ import annotations

from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3a1f7d82e94"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("problems_v2", "problems")
    op.rename_table("solutions_v2", "solutions")
    op.rename_table("outcomes_v2", "outcomes")


def downgrade() -> None:
    op.rename_table("outcomes", "outcomes_v2")
    op.rename_table("solutions", "solutions_v2")
    op.rename_table("problems", "problems_v2")
