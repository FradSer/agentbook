"""enforce outcome.kind NOT NULL with CHECK constraint

Revision ID: k4d5e6f7a8b9
Revises: j3c4d5e6f7a8
Create Date: 2026-05-05 09:00:00.000000

Release N+2 of the three-release zero-downtime schedule. Pre-flight
check refuses the migration when any row still has ``kind IS NULL`` so
operators are pointed at the backfill monitor instead of a mid-run
failure. The column was already created ``NOT NULL`` in release N for
new rows, but legacy environments that skipped release N+1 may still
hold nulls; this guard makes the outcome deterministic.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "k4d5e6f7a8b9"
down_revision = "j3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    null_count = bind.execute(
        sa.text("SELECT count(*) FROM outcomes WHERE kind IS NULL")
    ).scalar()
    if null_count and int(null_count) > 0:
        raise RuntimeError(
            f"Cannot enforce NOT NULL: {null_count} outcomes row(s) still have "
            "kind IS NULL. Run the release N+1 backfill to completion first "
            "(alembic revision j3c4d5e6f7a8)."
        )
    # Column is already NOT NULL from release N; keep the op idempotent.
    op.alter_column("outcomes", "kind", nullable=False)
    op.create_check_constraint(
        "outcomes_kind_check",
        "outcomes",
        "kind IN ('observed', 'verified')",
    )


def downgrade() -> None:
    op.drop_constraint("outcomes_kind_check", "outcomes", type_="check")
    # Do NOT relax NOT NULL on downgrade — release N already set it.
