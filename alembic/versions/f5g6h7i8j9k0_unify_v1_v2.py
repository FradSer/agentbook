"""Unify V1/V2: drop Thread/Comment/Vote tables, add review fields to Problem/Solution.

Revision ID: f5g6h7i8j9k0
Revises: 4b624264d69e
Create Date: 2026-03-19 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "f5g6h7i8j9k0"
down_revision = "4b624264d69e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add review fields to problems
    op.add_column("problems", sa.Column("review_status", sa.String(20), nullable=True))
    op.add_column("problems", sa.Column("review_score", sa.Float(), nullable=True))
    op.add_column(
        "problems", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "problems",
        sa.Column("canonical_solution_id", sa.String(36), nullable=True),
    )

    # Add review fields to solutions
    op.add_column("solutions", sa.Column("review_status", sa.String(20), nullable=True))
    op.add_column("solutions", sa.Column("review_score", sa.Float(), nullable=True))
    op.add_column(
        "solutions", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "solutions",
        sa.Column(
            "environment_scores",
            sa.JSON(),
            nullable=False,
            server_default="{}",
        ),
    )

    # Add self-parent check constraint on solutions
    op.create_check_constraint(
        "ck_no_self_parent",
        "solutions",
        "parent_solution_id != solution_id",
    )

    # Rename related_comment_id -> related_solution_id in token_transactions
    op.add_column(
        "token_transactions",
        sa.Column("related_solution_id", sa.String(36), nullable=True),
    )
    # Copy data from old column (if any rows exist)
    op.execute(
        "UPDATE token_transactions SET related_solution_id = related_comment_id "
        "WHERE related_comment_id IS NOT NULL"
    )
    op.drop_column("token_transactions", "related_comment_id")

    # Drop V1 tables (order matters for FK constraints)
    op.drop_table("votes")
    op.drop_table("comments")
    op.drop_table("threads")


def downgrade() -> None:
    raise NotImplementedError("This migration cannot be reversed")
