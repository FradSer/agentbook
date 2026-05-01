# Task 003: Alembic migration for ix_problems_research_started_at partial index

**depends-on**: 002

## Description

Add an Alembic migration that creates the partial index keeping `list_being_researched` queries sub-millisecond. The index is partial because `research_started_at` is mostly NULL. `CREATE INDEX CONCURRENTLY` is inherently zero-downtime; the migration's docstring documents the rollback procedure for an interrupted `CONCURRENTLY` run.

## Execution Context

**Task Number**: 003 of 20
**Phase**: Foundation — Database
**Prerequisites**: Task 002 (Protocol methods declared so the index has a query to support).

## BDD Scenario

The migration enables this scenario at acceptable cost:

```gherkin
Scenario: list_being_researched honours the 360s window
  Given problem "A" has research_started_at 359 seconds ago
  And problem "B" has research_started_at 361 seconds ago
  And problem "C" has research_started_at set to NULL
  When list_being_researched is called with timeout_seconds=360
  Then the result includes "A"
  And the result excludes "B"
  And the result excludes "C"
```

The index does not change behaviour, only performance. It is required by the per-connection 2-second poll model (each connection drives one filtered SELECT per tick).

**Spec Source**: `../2026-05-01-live-research-banner-design/bdd-specs.md`
**Architecture Source**: `../2026-05-01-live-research-banner-design/architecture.md` §2 + §7 Risk 1

## Files to Modify/Create

- Create: `alembic/versions/<NEW>_add_problems_research_started_at_index.py` (Alembic generates the timestamp prefix; pick a stable revision id e.g. `a1b2c3d4e5f6`)
- Modify: `backend/infrastructure/persistence/sqlalchemy_models.py:126` (add `index=True` on the `research_started_at` Column for parity in dev / in-memory schema generation)

## Steps

### Step 1: Generate a new revision
```bash
uv run alembic revision -m "add ix_problems_research_started_at partial index"
```

### Step 2: Replace the body of the generated migration

The migration must use `CREATE INDEX CONCURRENTLY` with `WHERE research_started_at IS NOT NULL`, and must run outside a transaction (Alembic supports this via `op.execute` after marking the migration `transactional_ddl = False`).

Required signatures and shape (no implementation body — describe the contract):

```python
"""add ix_problems_research_started_at partial index

This index supports per-connection SSE polling for the Live Research Banner.
The partial predicate keeps the index small because research_started_at is
mostly NULL.

Rollback note: CREATE INDEX CONCURRENTLY leaves an INVALID index if
interrupted (network drop, OOM, deploy abort). Before re-running:

    DROP INDEX IF EXISTS ix_problems_research_started_at;

This script's down_revision drops the index unconditionally, which also
cleans up an INVALID index left behind by an interrupted forward run.
"""

revision: str = "<new>"
down_revision: str | None = "<previous head>"
branch_labels = None
depends_on = None

# Required so CONCURRENTLY runs outside a transaction
disable_ddl_transaction = True


def upgrade() -> None:
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_problems_research_started_at "
        "ON problems (research_started_at) "
        "WHERE research_started_at IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_problems_research_started_at")
```

### Step 3: Update the ORM column for parity
In `backend/infrastructure/persistence/sqlalchemy_models.py:126`, add `index=True` to the `research_started_at` Column so SQLite-backed dev runs and `Base.metadata.create_all` produce a matching (non-partial) index.

### Step 4: Verify migration runs both ways against a local Postgres
```bash
DATABASE_URL=postgresql://... uv run alembic upgrade head
DATABASE_URL=postgresql://... uv run alembic downgrade -1
DATABASE_URL=postgresql://... uv run alembic upgrade head
```

## Verification Commands

```bash
ls alembic/versions/ | grep "research_started_at_index"
uv run alembic check
uv run python -c "import re; src = open([p for p in __import__('pathlib').Path('alembic/versions').glob('*research_started_at_index*')][0]).read(); assert 'CONCURRENTLY' in src; assert 'WHERE research_started_at IS NOT NULL' in src; assert 'disable_ddl_transaction = True' in src"
```

## Success Criteria

- New migration file exists; revision is reachable from `head`.
- Migration uses `CREATE INDEX CONCURRENTLY` with the exact partial predicate.
- `disable_ddl_transaction = True` set so CONCURRENTLY runs outside a TX.
- `downgrade()` is `DROP INDEX IF EXISTS …`.
- Migration docstring includes the rollback note.
- ORM column gains `index=True` (parity for in-memory + SQLite dev).
- `alembic upgrade head` and `alembic downgrade -1` both succeed against local Postgres.
