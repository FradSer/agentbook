"""add_research_candidates_index

Revision ID: dd782cb96759
Revises: e5f6a7b8c9d0
Create Date: 2026-03-15 18:13:30.378941
"""
from __future__ import annotations

from alembic import op

revision = 'dd782cb96759'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Composite index for find_research_candidates query
    op.create_index(
        "idx_research_candidates",
        "problems",
        ["solution_count", "best_confidence"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_research_candidates", table_name="problems")
