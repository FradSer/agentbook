# Task 002a: Outcome.kind domain and hydration — Red

**depends-on**: 001

## Description

Add the failing unit tests that assert the `Outcome` domain dataclass carries a `kind` field with default `"observed"`, that the SQLAlchemy repository hydrates legacy rows where `kind IS NULL` as `"observed"`, and that persistence round-trips the field correctly. Tests should FAIL until task 002b lands.

## Execution Context

**Task Number**: 002a of 41
**Phase**: Foundation — Domain
**Prerequisites**: Task 001 applied so the `kind` column exists.

## BDD Scenario

```gherkin
Scenario: Legacy outcomes without kind are treated as observed
  Given an Outcome row loaded from persistence with kind IS NULL
  When the repository hydrates the domain object
  Then the resulting Outcome.kind is "observed"
  And the effective weight multiplier is 1.0
```

**Spec Source**: `../2026-04-18-memory-layer-autoresearch-design/bdd-specs.md`

## Files to Modify/Create

- Create: `backend/tests/unit/test_outcome_kind_domain.py`

## Steps

### Step 1: Verify scenario
- Confirm the Gherkin scenario above exists verbatim in `bdd-specs.md`.

### Step 2: Write failing tests (Red)
Contracts to assert:
- `Outcome(solution_id=..., reporter_id=..., success=True)` has `kind == "observed"` by default.
- `Outcome(..., kind="verified")` round-trips through `OutcomeORM` → `_to_outcome_domain` and back.
- When the ORM layer is handed a row with `kind IS NULL` (simulate by patching `getattr`), the hydrated domain object has `kind == "observed"`.
- `calculate_confidence` on an `Outcome(kind="observed")` returns the same value as today's code path (parity check against pre-refactor snapshot).

### Step 3: Confirm Red
- Run `uv run pytest backend/tests/unit/test_outcome_kind_domain.py -x` and confirm every new test FAILS with either `AttributeError: 'Outcome' object has no attribute 'kind'` or `TypeError: unexpected keyword argument 'kind'`.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_outcome_kind_domain.py -x
# Expected: FAILED (tests are red by design)
```

## Success Criteria

- Test file created and committed.
- Every test FAILS for the intended reason (missing `kind` field), not accidental errors.
- No modification to production code in this task.
