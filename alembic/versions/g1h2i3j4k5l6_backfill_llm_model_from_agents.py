"""backfill llm_model from agents.model_type

Revision ID: g1h2i3j4k5l6
Revises: f0a1b2c3d4e5
Create Date: 2026-03-23
"""

from __future__ import annotations

from alembic import op

revision = "g1h2i3j4k5l6"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL: join-update from agents for existing rows that have no llm_model yet.
    op.execute(
        """
        UPDATE solutions AS s
        SET llm_model = a.model_type
        FROM agents AS a
        WHERE s.author_id = a.agent_id
          AND s.llm_model IS NULL
          AND a.model_type IS NOT NULL
          AND btrim(a.model_type) <> ''
        """
    )
    op.execute(
        """
        UPDATE research_cycles AS rc
        SET llm_model = a.model_type
        FROM agents AS a
        WHERE rc.researcher_id = a.agent_id
          AND rc.llm_model IS NULL
          AND a.model_type IS NOT NULL
          AND btrim(a.model_type) <> ''
        """
    )


def downgrade() -> None:
    # Cannot reliably restore previous NULL vs filled; leave data as-is on downgrade.
    pass
