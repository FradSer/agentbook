"""enforce (solution_id, reporter_id) uniqueness on outcomes

Revision ID: p1q2r3s4t5u6
Revises: n9o0p1q2r3s4
Create Date: 2026-05-13 18:00:00.000000

v6 confidence policy companion: the same reporter cannot vote twice
on the same solution. The pre-v6 behaviour let one agent push
confidence past 0.95 by repeating ``report_outcome`` for the same
``(solution_id, reporter_id)`` pair — each repeat appended a new row
and the unique-reporter count stayed at one but ``total`` grew, which
the Bayesian formula treated as a stronger signal.

The migration dedupes any historical duplicates first (most recent
row by ``created_at`` wins, ``weight`` is taken as ``max`` across the
collapsed group so a legitimate ``partial`` half-weight isn't
silently lost), then installs the UniqueConstraint. Going forward
``OutcomeRepository.upsert`` is the only safe write path.
"""

from __future__ import annotations

from sqlalchemy import text

from alembic import op

revision = "p1q2r3s4t5u6"
down_revision = "n9o0p1q2r3s4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # Dedupe historical rows. The CTE picks the surviving outcome_id per
    # (solution_id, reporter_id) by most-recent created_at, and rolls up
    # max(weight) onto it before the losers are deleted. SQLite (used in
    # unit-test migration replay) understands the same syntax.
    # Only winners whose group has a heavier sibling need a weight bump.
    # Skipping the no-op rewrite on solo rows keeps WAL bounded to the
    # actual duplicates instead of the entire outcomes table.
    bind.execute(
        text(
            """
            WITH ranked AS (
                SELECT
                    outcome_id,
                    weight,
                    ROW_NUMBER() OVER (
                        PARTITION BY solution_id, reporter_id
                        ORDER BY created_at DESC, outcome_id DESC
                    ) AS rn,
                    MAX(weight) OVER (
                        PARTITION BY solution_id, reporter_id
                    ) AS max_weight
                FROM outcomes
            )
            UPDATE outcomes
            SET weight = (
                SELECT max_weight FROM ranked
                WHERE ranked.outcome_id = outcomes.outcome_id
            )
            WHERE outcome_id IN (
                SELECT outcome_id FROM ranked
                WHERE rn = 1 AND max_weight > weight
            )
            """
        )
    )
    bind.execute(
        text(
            """
            DELETE FROM outcomes
            WHERE outcome_id IN (
                SELECT outcome_id
                FROM (
                    SELECT
                        outcome_id,
                        ROW_NUMBER() OVER (
                            PARTITION BY solution_id, reporter_id
                            ORDER BY created_at DESC, outcome_id DESC
                        ) AS rn
                    FROM outcomes
                ) ranked
                WHERE rn > 1
            )
            """
        )
    )

    op.create_unique_constraint(
        "uq_outcome_reporter_solution",
        "outcomes",
        ["solution_id", "reporter_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_outcome_reporter_solution",
        "outcomes",
        type_="unique",
    )
