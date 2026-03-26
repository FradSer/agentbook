"""Add research loop fields: parent_solution_id + research_cycles table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-15

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "solutions",
        sa.Column("parent_solution_id", sa.String(36), sa.ForeignKey("solutions.solution_id"), nullable=True),
    )

    # Add constraint to prevent self-loops
    op.create_check_constraint(
        "ck_solutions_no_self_parent",
        "solutions",
        "parent_solution_id != solution_id",
    )

    op.create_table(
        "research_cycles",
        sa.Column("cycle_id", sa.String(36), primary_key=True),
        sa.Column(
            "problem_id",
            sa.String(36),
            sa.ForeignKey("problems.problem_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "researcher_id",
            sa.String(36),
            sa.ForeignKey("agents.agent_id"),
            nullable=False,
        ),
        sa.Column(
            "proposed_solution_id",
            sa.String(36),
            sa.ForeignKey("solutions.solution_id"),
            nullable=True,
        ),
        sa.Column("previous_best_confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("new_confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("research_cycles")
    op.drop_constraint("ck_solutions_no_self_parent", "solutions", type_="check")
    op.drop_column("solutions", "parent_solution_id")
