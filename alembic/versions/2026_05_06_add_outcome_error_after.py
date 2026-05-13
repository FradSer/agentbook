"""add outcome.error_after column

Revision ID: l5e6f7a8b9c0
Revises: m6f7a8b9cabd
Create Date: 2026-05-06 09:00:00.000000

The domain ``Outcome`` carries ``error_after`` (the residual error string
left after applying a solution) but the ORM never had a column, so the
field was silently dropped on persist. Adding it as nullable Text keeps
existing rows valid while letting verified-outcome paths capture residual
diagnostics.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "l5e6f7a8b9c0"
down_revision = "m6f7a8b9cabd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "outcomes",
        sa.Column("error_after", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("outcomes", "error_after")
