"""Drop unused columns: reputation, error_after, environment_scores

Revision ID: c3a1f7d82e94
Revises: bdf1f1e79252
Create Date: 2026-02-28

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c3a1f7d82e94"
down_revision = "bdf1f1e79252"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("agents", "reputation")
    op.drop_column("outcomes_v2", "error_after")
    op.drop_column("solutions_v2", "environment_scores")


def downgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("reputation", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "outcomes_v2",
        sa.Column("error_after", sa.Text(), nullable=True),
    )
    op.add_column(
        "solutions_v2",
        sa.Column("environment_scores", sa.JSON(), nullable=False, server_default="{}"),
    )
