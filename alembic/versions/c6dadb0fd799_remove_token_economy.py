"""remove token economy

Drops the agents.token_balance column and the token_transactions table.
The token economy was removed in the public-memory pivot — confidence is
now driven entirely by Bayesian outcome scoring (see
backend/application/confidence.py).

Revision ID: c6dadb0fd799
Revises: 7e8a50adfe56
Create Date: 2026-04-13 15:26:37.997092
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "c6dadb0fd799"
down_revision = "7e8a50adfe56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "token_transactions" in inspector.get_table_names():
        op.drop_table("token_transactions")

    agent_columns = {col["name"] for col in inspector.get_columns("agents")}
    if "token_balance" in agent_columns:
        with op.batch_alter_table("agents") as batch_op:
            batch_op.drop_column("token_balance")


def downgrade() -> None:
    with op.batch_alter_table("agents") as batch_op:
        batch_op.add_column(
            sa.Column(
                "token_balance",
                sa.Integer(),
                nullable=False,
                server_default="100",
            )
        )

    op.create_table(
        "token_transactions",
        sa.Column("tx_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "agent_id",
            sa.String(length=36),
            sa.ForeignKey("agents.agent_id"),
            nullable=False,
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("tx_type", sa.String(length=50), nullable=False),
        sa.Column("related_solution_id", sa.String(length=36), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
