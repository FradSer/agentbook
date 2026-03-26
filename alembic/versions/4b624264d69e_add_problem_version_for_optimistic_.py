"""add_problem_version_for_optimistic_locking

Revision ID: 4b624264d69e
Revises: dd782cb96759
Create Date: 2026-03-15 19:13:40.724155
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = '4b624264d69e'
down_revision = 'dd782cb96759'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add version column for optimistic locking
    op.add_column(
        "problems",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("problems", "version")
