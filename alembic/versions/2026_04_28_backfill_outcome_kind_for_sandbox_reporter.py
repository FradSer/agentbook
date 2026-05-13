"""backfill outcome.kind = 'verified' for historical SANDBOX_AGENT_ID outcomes

Revision ID: j3c4d5e6f7a8
Revises: i2b3c4d5e6f7
Create Date: 2026-04-28 09:00:00.000000

Release N+1 of the three-release zero-downtime schedule. The release N
migration added the column with ``server_default='observed'`` so new
rows are already correct. Rows written before release N retained their
defaulted value, including sandbox-produced outcomes that should be
``verified``. This revision paginates the update by ``ctid`` in batches
of 10,000 so the lock duration per batch stays under 500ms on a
production-sized table. Re-running the migration after a mid-run
failure resumes from the last committed batch because each batch is
an independent statement, and the WHERE clause is idempotent.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "j3c4d5e6f7a8"
down_revision = "i2b3c4d5e6f7"
branch_labels = None
depends_on = None

SANDBOX_AGENT_ID = "00000000-0000-0000-0000-000000000003"
BATCH_SIZE = 10_000


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite in dev has no ctid; fall back to a single statement.
        bind.execute(
            sa.text(
                "UPDATE outcomes SET kind = 'verified' "
                "WHERE reporter_id = :sid AND kind IS DISTINCT FROM 'verified'"
            ),
            {"sid": SANDBOX_AGENT_ID},
        )
        return

    # Paginate by ctid for bounded lock windows.
    last_ctid = "(0,0)"
    while True:
        result = bind.execute(
            sa.text(
                """
                WITH batch AS (
                    SELECT ctid FROM outcomes
                    WHERE reporter_id = :sid
                      AND kind IS DISTINCT FROM 'verified'
                      AND ctid > :last_ctid
                    ORDER BY ctid
                    LIMIT :lim
                )
                UPDATE outcomes
                SET kind = 'verified'
                FROM batch
                WHERE outcomes.ctid = batch.ctid
                RETURNING outcomes.ctid
                """
            ),
            {"sid": SANDBOX_AGENT_ID, "last_ctid": last_ctid, "lim": BATCH_SIZE},
        )
        rows = result.fetchall()
        if not rows:
            break
        last_ctid = str(max(r[0] for r in rows))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("UPDATE outcomes SET kind = 'observed' WHERE reporter_id = :sid"),
        {"sid": SANDBOX_AGENT_ID},
    )
