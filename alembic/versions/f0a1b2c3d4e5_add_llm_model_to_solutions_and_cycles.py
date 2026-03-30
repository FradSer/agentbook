"""add llm_model to solutions and research_cycles

Revision ID: f0a1b2c3d4e5
Revises: e8f9a1b2c3d4
Create Date: 2026-03-23
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "f0a1b2c3d4e5"
down_revision = "e8f9a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "solutions", sa.Column("llm_model", sa.String(length=120), nullable=True)
    )
    op.add_column(
        "research_cycles", sa.Column("llm_model", sa.String(length=120), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("research_cycles", "llm_model")
    op.drop_column("solutions", "llm_model")
