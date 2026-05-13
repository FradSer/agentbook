"""drop solutions.environment_scores

Revision ID: m6f7a8b9cabd
Revises: l5e6f7a8b9ca
Create Date: 2026-04-23
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "m6f7a8b9cabd"
down_revision = "l5e6f7a8b9ca"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("solutions", "environment_scores")


def downgrade() -> None:
    op.add_column(
        "solutions",
        sa.Column(
            "environment_scores",
            sa.JSON(),
            nullable=False,
            server_default="{}",
        ),
    )
    op.alter_column("solutions", "environment_scores", server_default=None)
