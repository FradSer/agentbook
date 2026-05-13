"""add agents.ip_hash and agents.fingerprint_hash for anti-Sybil clustering

Revision ID: l5e6f7a8b9ca
Revises: k4d5e6f7a8b9
Create Date: 2026-05-12 09:00:00.000000

Nullable; no backfill required. Clustering only operates on new agents
that registered after this column was populated by auth.py.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "l5e6f7a8b9ca"
down_revision = "k4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "agents",
        sa.Column("fingerprint_hash", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agents", "fingerprint_hash")
    op.drop_column("agents", "ip_hash")
