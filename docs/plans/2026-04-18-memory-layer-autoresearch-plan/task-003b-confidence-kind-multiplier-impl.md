# Task 003b: calculate_confidence kind_multiplier — Green

**depends-on**: 003a

## Description

Extend `calculate_confidence` to multiply each outcome's base weight by `kind_multiplier`, defined as `2.0` for `kind == "verified"` and `1.0` otherwise. Preserve the external-reporter diversity check — `SANDBOX_AGENT_ID` outcomes continue to count as external because `reporter_id != author_id` holds.

## Execution Context

**Task Number**: 003b of 41
**Phase**: Foundation — Confidence weighting
**Prerequisites**: Task 003a red tests committed.

## BDD Scenario

(Same three scenarios as task 003a — see `bdd-specs.md`.)

## Files to Modify/Create

- Modify: `backend/application/confidence.py::calculate_confidence` — add `kind_multiplier` factor in the per-outcome loop.

## Steps

### Step 1: Add multiplier
- Inside the `for outcome in outcomes:` loop, add:
  ```python
  kind_multiplier = 2.0 if outcome.kind == "verified" else 1.0
  final_weight = base_weight * kind_multiplier * recency_factor * env_factor
  ```
  Leave the existing `base_weight` (self-report dampener) and `recency_factor` calculations intact.

### Step 2: Update docstring
- Extend the function docstring to document the `kind_multiplier` factor and reference `bdd-specs.md`. Do not add implementation commentary inside the loop — the multiplier expression is self-documenting.

### Step 3: Run tests green
- Run the test file from 003a and the broader unit suite:
  ```
  uv run pytest backend/tests/unit/test_confidence_kind_multiplier.py
  uv run pytest backend/tests/unit/test_confidence_scoring.py
  uv run pytest backend/tests/unit/
  ```
- Update any tests in `test_confidence_scoring.py` that constructed `Outcome` objects without `kind` so they pass. If any pre-existing golden-like test snapshots drift, record the new values in the commit message.

### Step 4: Property-test hook
- Add a Hypothesis property test (in the same file or a new `test_confidence_properties.py`): for any non-empty list of outcomes with arbitrary `kind` values, `calculate_confidence ∈ [0.0, 1.0]`, monotonic on success addition, and changing one observed → verified never lowers confidence.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_confidence_kind_multiplier.py -v
uv run pytest backend/tests/unit/test_confidence_scoring.py
uv run pytest backend/tests/unit/
uv run ruff check backend/application/confidence.py
```

## Success Criteria

- All tests in 003a pass.
- Hypothesis property tests pass with 200+ examples.
- No regression in `test_confidence_scoring.py`.
- `confidence.py` imports remain bounded to `backend/domain/` + stdlib (immutability rule).
