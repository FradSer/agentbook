"""drop_solution_author_verified

Revision ID: e8f9a1b2c3d4
Revises: dab0405cde18
Create Date: 2026-03-23
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "e8f9a1b2c3d4"
down_revision = "dab0405cde18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("solutions", "author_verified")


def downgrade() -> None:
    op.add_column(
        "solutions",
        sa.Column(
            "author_verified", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.alter_column("solutions", "author_verified", server_default=None)
