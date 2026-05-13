# Task 002b: Outcome.kind domain and hydration — Green

**depends-on**: 002a

## Description

Add `kind: str = "observed"` to the `Outcome` domain dataclass, the matching SQLAlchemy mapped column, and the repository hydration logic. The defensive `getattr(row, "kind", "observed")` lives here for the duration of the migration window. After this task, every test in 002a passes.

## Execution Context

**Task Number**: 002b of 41
**Phase**: Foundation — Domain
**Prerequisites**: Task 002a's failing tests are committed and reproducible.

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

- Modify: `backend/domain/models.py` — add `kind: str = "observed"` to `Outcome` dataclass.
- Modify: `backend/infrastructure/persistence/sqlalchemy_models.py::OutcomeORM` — add `kind: Mapped[str] = mapped_column(String(10), server_default="observed", nullable=False)`.
- Modify: `backend/infrastructure/persistence/sqlalchemy_repositories.py::_to_outcome_domain` — read `kind=getattr(row, "kind", "observed")`.

## Steps

### Step 1: Update domain dataclass
- Insert `kind: str = "observed"` in `Outcome` before the `outcome_id` default. Keep positional constructor compatibility — add a comment `# Placed before outcome_id to preserve positional construction`.

### Step 2: Update ORM model
- Add the `kind` column with `server_default="observed"`, `nullable=False`, `String(10)`. Verify autogenerate-drift check stays clean (compare-by-signature).

### Step 3: Update repository hydration
- Replace the current direct access with `getattr(row, "kind", "observed")`. This is the only defensive branch; it will be removed in release N+2 (task 021).

### Step 4: Update API response serialization
- In `backend/presentation/api/schemas.py`, extend the `OutcomeResponse` Pydantic model to include `kind: Literal["observed", "verified"]` so the frontend can render verified badges. Input schemas (`OutcomeCreateRequest`) MUST NOT expose `kind` — it is server-derived (task 004b).

### Step 5: Run tests green
- Run `uv run pytest backend/tests/unit/test_outcome_kind_domain.py` and confirm all tests PASS.
- Run `uv run pytest backend/tests/unit/` to confirm no collateral regression.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_outcome_kind_domain.py -v
uv run pytest backend/tests/unit/
uv run ruff check backend/domain/models.py backend/infrastructure/persistence/
```

## Success Criteria

- All tests from task 002a pass.
- No other unit tests regress.
- Ruff + type check clean.
- API response includes `kind` on outcomes; API request does not accept `kind`.
