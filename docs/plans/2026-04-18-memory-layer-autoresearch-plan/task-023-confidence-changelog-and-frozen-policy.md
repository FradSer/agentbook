# Task 023: confidence-changelog.md and @frozen_policy marker

**depends-on**: 003b

## Description

Create `docs/confidence-changelog.md` as the append-only authority for scoring-policy changes. Add a `@frozen_policy("v4")` decorator on `calculate_confidence` — a runtime no-op whose version string is checked by a CI grep test against the changelog. Any future bump without a matching changelog entry fails the build. Also create the Hypothesis golden-file test harness for `confidence.py`.

## Execution Context

**Task Number**: 023 of 41
**Phase**: Policy hygiene
**Prerequisites**: Task 003b committed.

## BDD Scenario

No direct BDD scenario. This task enforces the best-practice from design `best-practices.md §5` that makes scoring-policy drift detectable in CI.

**Spec Source**: `../2026-04-18-memory-layer-autoresearch-design/best-practices.md` §5

## Files to Modify/Create

- Create: `docs/confidence-changelog.md`
- Create: `backend/application/_frozen_policy.py` — decorator definition.
- Modify: `backend/application/confidence.py::calculate_confidence` — apply `@frozen_policy("v4")`.
- Create: `backend/tests/unit/test_confidence_golden.py` — golden-file snapshots for 50 fixture inputs.
- Create: `scripts/check_frozen_policy.sh` — CI grep verifying changelog contains the current version.

## Steps

### Step 1: Changelog
- Initial entries:
  - `v1` — original Bayesian `calculate_confidence` shipped 2025-12-xx.
  - `v2` — external-reporter requirement (2026-04-01 post-mortem fix).
  - `v3` — placeholder (skip if no history applies).
  - `v4` — `Outcome.kind` multiplier + reporter clustering (this plan).
- Each entry: date, version, summary, link to plan/PR, behaviour change description.

### Step 2: @frozen_policy decorator
- Signature:
  ```python
  def frozen_policy(version: str) -> Callable[[F], F]:
      """No-op decorator carrying a version marker for CI guard."""
      def decorator(fn):
          fn.__frozen_policy_version__ = version
          return fn
      return decorator
  ```

### Step 3: Apply + import
- `calculate_confidence = frozen_policy("v4")(calculate_confidence)` — or use the `@frozen_policy("v4")` syntax directly above the function.
- Add import: `from backend.application._frozen_policy import frozen_policy` (this stays within `backend/application/` so `confidence.py`'s import-cleanliness rule is respected — the decorator is zero-dep).

### Step 4: Golden-file harness
- `test_confidence_golden.py` ships 50 curated fixtures (varying outcome counts, kinds, recency, reporter diversity). Each fixture snapshots `calculate_confidence` output to 4 decimal places. Failing the snapshot forces `--update-golden` + a PR note.

### Step 5: CI guard script
- `scripts/check_frozen_policy.sh`:
  ```bash
  VERSION=$(python -c "from backend.application.confidence import calculate_confidence; print(calculate_confidence.__frozen_policy_version__)")
  grep -q "^## $VERSION" docs/confidence-changelog.md || {
      echo "ERROR: frozen_policy version $VERSION missing from changelog"
      exit 1
  }
  ```
- Wire into `make fast` or `make full` so the check runs on every PR.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_confidence_golden.py
bash scripts/check_frozen_policy.sh
```

## Success Criteria

- Changelog file committed with v1-v4 history.
- Version bump without changelog entry fails `scripts/check_frozen_policy.sh`.
- 50 golden fixtures pass today; any future math change flips at least one and forces `--update-golden`.
