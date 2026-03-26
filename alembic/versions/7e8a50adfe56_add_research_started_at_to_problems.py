"""add_research_started_at_to_problems

Revision ID: 7e8a50adfe56
Revises: g1h2i3j4k5l6
Create Date: 2026-03-23 03:05:36.280519
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = '7e8a50adfe56'
down_revision = 'g1h2i3j4k5l6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('problems', sa.Column('research_started_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('problems', 'research_started_at')
