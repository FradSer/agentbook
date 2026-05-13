# Task 021: Alembic N+2 NOT NULL switchover with pre-flight guard

**depends-on**: 005

## Description

Third and final migration. Flips `outcomes.kind` to `NOT NULL` and adds a `CHECK (kind IN ('observed', 'verified'))` constraint. Pre-flight guard refuses the migration if any row still has `kind IS NULL`. In the same release, removes the defensive `getattr(row, "kind", "observed")` branch from `sqlalchemy_repositories.py::_to_outcome_domain` so the code stops tolerating nulls.

## Execution Context

**Task Number**: 021 of 41
**Phase**: Migration — release N+2
**Prerequisites**: Task 005 applied; monitoring probe reports 24h of zero-nulls.

## BDD Scenario

```gherkin
Scenario: Release N+2 enforces NOT NULL after 24h of zero nulls
  Given a monitoring probe reports zero outcomes.kind IS NULL for 24h
  When the NOT NULL + CHECK migration runs
  Then outcomes.kind is NOT NULL
  And CHECK (kind IN ('observed', 'verified')) is enforced
  And the defensive NULL branch in calculate_confidence is removed in the same release

Scenario: NOT NULL switchover refuses to proceed while NULL rows exist
  Given at least one outcomes row still has kind IS NULL
  When the release N+2 migration is attempted
  Then the migration aborts with a pre-flight check error
  And no ALTER COLUMN statement runs
  And the operator is pointed at the backfill completion monitor
```

**Spec Source**: `../2026-04-18-memory-layer-autoresearch-design/bdd-specs.md`

## Files to Modify/Create

- Create: `alembic/versions/2026_05_05_outcome_kind_not_null_with_check.py`
- Modify: `backend/infrastructure/persistence/sqlalchemy_repositories.py::_to_outcome_domain` — remove the defensive `getattr` fallback.
- Create: `backend/tests/integration/test_migration_n2_not_null.py` (marked `@pytest.mark.smoke`).

## Steps

### Step 1: Pre-flight check
- `upgrade()` begins with:
  ```python
  conn = op.get_bind()
  null_count = conn.execute(sa.text(
      "SELECT count(*) FROM outcomes WHERE kind IS NULL"
  )).scalar()
  if null_count > 0:
      raise RuntimeError(
          f"Cannot enforce NOT NULL: {null_count} rows still have kind IS NULL. "
          "Run the release N+1 backfill to completion first."
      )
  ```
- This is executable intent — executor implements the exact syntax.

### Step 2: ALTER COLUMN and CHECK
```python
op.alter_column("outcomes", "kind", nullable=False)
op.create_check_constraint(
    "outcomes_kind_check",
    "outcomes",
    "kind IN ('observed', 'verified')",
)
```

### Step 3: Remove defensive read path
- In `_to_outcome_domain`, change `kind=getattr(row, "kind", "observed")` to `kind=row.kind`. If the field becomes implicit via ORM hydration, remove the line.

### Step 4: Downgrade
- `downgrade()` drops the CHECK constraint and re-allows NULL. Does NOT re-add the defensive branch — rollback implies stopping at release N+1 code, not below.

### Step 5: Smoke test pre-flight abort
- Seed a Docker PostgreSQL with 50 outcomes, leave 1 with `kind IS NULL`. Run `alembic upgrade head`; assert it raises with the pre-flight message and the `ALTER COLUMN` never ran.

### Step 6: Smoke test happy path
- Seed 50 outcomes all with non-null kind; migration succeeds; CHECK constraint is enforceable (inserting `kind='invalid'` fails).

## Verification Commands

```bash
uv run alembic upgrade head
RUN_DOCKER_TESTS=1 uv run pytest backend/tests/integration/test_migration_n2_not_null.py -v
```

## Success Criteria

- Migration applies cleanly when zero nulls.
- Migration refuses and reports the null count when any null exists.
- CHECK constraint rejects invalid `kind` values.
- Defensive `getattr` removed from read path.
