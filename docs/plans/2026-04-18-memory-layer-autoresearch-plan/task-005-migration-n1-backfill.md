# Task 005: Alembic N+1 backfill with resumable batches

**depends-on**: 003b, 004b

## Description

Second Alembic revision. Backfills `kind = 'verified'` on historical outcomes where `reporter_id = SANDBOX_AGENT_ID`, in ctid-paginated batches of 10,000 to cap per-batch lock duration under 500ms. Resumable on failure: re-running the migration continues from the last committed ctid. Also flips `calculate_confidence` to read `kind` from persistence with a defensive `NULL → "observed"` branch for the migration window.

## Execution Context

**Task Number**: 005 of 41
**Phase**: Foundation — Backfill
**Prerequisites**: Tasks 001, 002b, 003b, 004b applied.

## BDD Scenario

```gherkin
Scenario: Release N+1 backfills verified outcomes
  Given rows exist with reporter_id = SANDBOX_AGENT_ID and kind IS NULL
  When the backfill script runs in batches of 10,000
  Then all such rows have kind = "verified"
  And no row is locked for more than 500ms per batch
  And calculate_confidence handles NULL defensively (treats as "observed")

Scenario: Backfill batch fails mid-run
  Given the release N+1 backfill has updated 30,000 of 80,000 legacy rows
  And batch 4 fails because of a lock-timeout on a long-running analytic query
  When the operator re-runs the migration
  Then the backfill resumes from the last committed ctid
  And no row is updated twice
  And calculate_confidence continues to return correct values throughout
    (mixed NULL + filled rows are handled by the defensive "observed" fallback)
```

**Spec Source**: `../2026-04-18-memory-layer-autoresearch-design/bdd-specs.md`

## Files to Modify/Create

- Create: `alembic/versions/2026_04_28_backfill_outcome_kind_for_sandbox_reporter.py`
- Create: `backend/tests/integration/test_migration_n1_backfill.py` (smoke test against Docker PostgreSQL, marked `@pytest.mark.smoke`).

## Steps

### Step 1: Write the migration
- `upgrade()` loops over ctid ranges:
  ```python
  def upgrade():
      conn = op.get_bind()
      last_ctid = "(0,0)"
      while True:
          result = conn.execute(sa.text("""
              UPDATE outcomes SET kind = 'verified'
              WHERE ctid IN (
                SELECT ctid FROM outcomes
                WHERE reporter_id = :sandbox_id
                  AND kind IS DISTINCT FROM 'verified'
                  AND ctid > :last_ctid
                ORDER BY ctid
                LIMIT 10000
              )
              RETURNING ctid
          """), {"sandbox_id": SANDBOX_AGENT_ID, "last_ctid": last_ctid})
          rows = result.fetchall()
          if not rows:
              break
          last_ctid = str(max(row.ctid for row in rows))
  ```
  Intent only — executor writes the working syntax. Resumability comes from the fact that each `UPDATE` commits independently via the default Alembic transaction handling.

- `downgrade()` resets verified-by-sandbox rows back to observed (idempotent; the backfill can be re-run after downgrade).

### Step 2: Defensive read path
- In `backend/infrastructure/persistence/sqlalchemy_repositories.py::_to_outcome_domain`, the `getattr(row, "kind", "observed")` from task 002b already handles the NULL defensive case. Confirm by inspection — no new code change here, but add a unit test asserting that a row with `kind = None` hydrates as `Outcome.kind == "observed"`.

### Step 3: Smoke test
- `test_migration_n1_backfill.py` starts a Docker PostgreSQL, seeds 100 sandbox + 100 non-sandbox outcomes with `kind = NULL`, runs `alembic upgrade head`, asserts all sandbox rows flip to `verified` and non-sandbox stay NULL (they will be handled by defensive `getattr` until release N+2).

### Step 4: Smoke resume
- Seed 30k sandbox outcomes. Run the migration with `RAISE_AFTER_BATCH=2` patched in (via pytest monkeypatch) to simulate mid-run failure. Re-run the migration and assert (a) no row is touched twice, (b) the final row count with `kind = "verified"` equals 30k.

## Verification Commands

```bash
# Locally
uv run alembic upgrade head
psql "$DATABASE_URL" -c "SELECT kind, count(*) FROM outcomes GROUP BY kind"

# Integration
RUN_DOCKER_TESTS=1 uv run pytest backend/tests/integration/test_migration_n1_backfill.py -v
```

## Success Criteria

- Migration applies and backfills sandbox-reporter rows to `verified`.
- Non-sandbox legacy rows remain `NULL` (release N+2 will not-null them after backfill completion).
- Mid-run failure resumes cleanly on re-run with no double-update.
- `calculate_confidence` returns correct values against a mixed-NULL table.
