"""add outcome.kind column with server default observed

Revision ID: i2b3c4d5e6f7
Revises: h1a2b3c4d5e6
Create Date: 2026-04-21 09:00:00.000000

Release N of the three-release zero-downtime schedule for
``outcome.kind``. Adds the column with ``server_default='observed'`` and
``NOT NULL`` so existing rows get the default without a table rewrite
(PostgreSQL 11+ applies constant defaults as metadata only). Release N-1
application code continues to work because it does not reference the
column.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "i2b3c4d5e6f7"
down_revision = "h1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "outcomes",
        sa.Column(
            "kind",
            sa.String(length=10),
            server_default="observed",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("outcomes", "kind")
