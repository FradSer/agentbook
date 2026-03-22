"""add_solution_promotion_status

Revision ID: dab0405cde18
Revises: f5g6h7i8j9k0
Create Date: 2026-03-22 17:46:08.552264
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'dab0405cde18'
down_revision = 'f5g6h7i8j9k0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('solutions', sa.Column('promotion_status', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('solutions', 'promotion_status')
