# Task 003a: calculate_confidence kind_multiplier — Red

**depends-on**: 002b

## Description

Write failing unit tests that pin the verified/observed weight ratio in `calculate_confidence`. Verified outcomes contribute 2× the base weight, observed keep 1×, and a verified-only history still passes the external-reporter diversity check because `SANDBOX_AGENT_ID` counts as trusted-external.

## Execution Context

**Task Number**: 003a of 41
**Phase**: Foundation — Confidence weighting
**Prerequisites**: Task 002b in place so `Outcome.kind` exists.

## BDD Scenario

```gherkin
Scenario: Verified outcome doubles base weight
  Given a solution with one Outcome(kind="verified", success=True)
  When calculate_confidence runs
  Then that outcome contributes 2.0 * base_weight to the weighted sum

Scenario: Observed outcome keeps base weight
  Given a solution with one Outcome(kind="observed", success=True)
  When calculate_confidence runs
  Then that outcome contributes 1.0 * base_weight to the weighted sum

Scenario: Verified-only history passes the external-reporter check
  Given a solution with three Outcome(kind="verified", reporter_id=SANDBOX_AGENT_ID)
  And zero observed outcomes
  When calculate_confidence runs
  Then unique_ext_reporters >= 1 (SANDBOX_AGENT_ID counts)
  And confidence is raised above the 0.3 baseline
```

**Spec Source**: `../2026-04-18-memory-layer-autoresearch-design/bdd-specs.md`

## Files to Modify/Create

- Create: `backend/tests/unit/test_confidence_kind_multiplier.py`

## Steps

### Step 1: Write three failing tests (one per scenario)
- `test_verified_outcome_doubles_base_weight` — construct author + one verified success outcome from a distinct reporter; compute confidence twice (once treating outcome as verified, once as observed) and assert `verified_confidence > observed_confidence` with a gap consistent with a 2× weight.
- `test_observed_outcome_keeps_base_weight` — assert observed outcome confidence matches the pre-refactor golden snapshot at `backend/tests/unit/test_confidence_golden.py` (if the golden file does not yet exist, create a placeholder marker for it in this task; full golden harness lives in task 023).
- `test_verified_only_history_passes_diversity` — three verified outcomes from `SANDBOX_AGENT_ID`, zero observed; assert `confidence > 0.3` and that no assertion references external-reporter count directly (treat that as an implementation detail).

### Step 2: Confirm Red
- Run `uv run pytest backend/tests/unit/test_confidence_kind_multiplier.py -x`; all three tests must FAIL because `calculate_confidence` currently ignores `kind`.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_confidence_kind_multiplier.py -x
# Expected: 3 failed
```

## Success Criteria

- Three tests authored, all failing for the correct reason.
- No production code modified.
