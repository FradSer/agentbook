# Task 001: Alembic N additive column for outcome.kind

**depends-on**: (none)

## Description

Add the `kind` column to the `outcomes` table with `server_default='observed'` and `NOT NULL` from day one. PostgreSQL 11+ treats constant defaults as metadata, so no table rewrite occurs and release N-1 application code keeps working (it does not read the column). This is release N of the three-release migration.

## Execution Context

**Task Number**: 001 of 41
**Phase**: Setup / Foundation
**Prerequisites**: Alembic is already wired in `alembic.ini` and `alembic/env.py`; `uv run alembic upgrade head` succeeds on a clean database.

## BDD Scenario

```gherkin
Scenario: Release N adds kind with server default
  When the migration runs
  Then outcomes.kind exists with type varchar(10) and default 'observed'
  And no existing rows are rewritten (PostgreSQL 11+ metadata-only default)
  And release N-1 application code still works against the new schema

Scenario: Rollback to release N is safe during the backfill window
  Given release N+1 is partially deployed and the backfill has updated 50% of rows
  When a rolling-deploy rollback returns the API to release N code
  Then release N's calculate_confidence still runs (it did not read kind)
  And no data corruption results
  And the operator can re-deploy N+1 without repeating the completed backfill batches
```

**Spec Source**: `../2026-04-18-memory-layer-autoresearch-design/bdd-specs.md`

## Files to Modify/Create

- Create: `alembic/versions/2026_04_21_add_outcome_kind_column_default_observed.py`

## Steps

### Step 1: Generate revision scaffold
- Run `uv run alembic revision -m "add outcome kind column default observed"` to scaffold the file. Rename the auto-generated filename to `2026_04_21_add_outcome_kind_column_default_observed.py` so the date prefix matches the three-release schedule.

### Step 2: Write upgrade
- `upgrade()` adds the column:
  ```python
  op.add_column(
      "outcomes",
      sa.Column("kind", sa.String(length=10), server_default="observed", nullable=False),
  )
  ```

### Step 3: Write downgrade
- `downgrade()` drops the column:
  ```python
  op.drop_column("outcomes", "kind")
  ```

### Step 4: Verify metadata-only default
- On a copy of production-sized data (or a seeded local DB with ≥10k rows), run `EXPLAIN (ANALYZE, BUFFERS) INSERT` against a newly-loaded row, then run the migration and time it. Assert the migration is `< 100ms` on a 100k-row table. Record the observation in the commit message.

### Step 5: Smoke the rollback scenario
- With release N+1 code checked out but the N+1 migration NOT yet applied, run the N+1 backfill against N's schema; confirm it errors cleanly. Then confirm release N-1 code continues to function against the N schema (read `outcomes` without selecting `kind`).

## Verification Commands

```bash
# Apply migration on a test DB
uv run alembic upgrade head

# Confirm column present
psql "$DATABASE_URL" -c "\d outcomes" | grep kind

# Ensure no rows were rewritten (ctid should be unchanged for existing rows)
psql "$DATABASE_URL" -c "SELECT ctid, id FROM outcomes LIMIT 5"

# Downgrade and reapply
uv run alembic downgrade -1 && uv run alembic upgrade head
```

## Success Criteria

- Migration applies and reverses cleanly on a local PostgreSQL 14+ instance.
- Column exists with `VARCHAR(10)`, `NOT NULL`, `DEFAULT 'observed'`.
- Zero rows rewritten (ctid unchanged for pre-existing rows).
- Release N-1 application code continues to read/write `outcomes` without referencing `kind`.
