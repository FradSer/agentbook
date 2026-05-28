# Task 014: evaluate_offline_rotate simulator tests (Feature 5)

**depends-on**: task-009

## Description

Add the Red tests for `evaluate_offline_rotate` in `pipeline/router.py`. Extend `experiments/agentbook-ab/pipeline/tests/test_router.py` with 3 tests covering all Feature 5 scenarios: rotate coverage at k=3 vs best static arm under LOO, sample-slot fallback when a slot is missing, and LOO safety in the rotate simulation. All new tests MUST fail Red.

This task is parallel-safe with the good_rotate/orchestrator chain (tasks 010-013) — it depends only on `select_arm_for_sample` from task-009 and exercises a pure simulator over the existing outcomes log.

## Execution Context

**Task Number**: 014 of 016
**Phase**: Batch 3 — Adaptive Sample Rotation (RED, offline simulator)
**Prerequisites**:
- task-009 complete: `select_arm_for_sample` available on both routers.

## BDD Scenario

```gherkin
Feature: evaluate_offline_rotate simulates good_rotate against the existing outcomes log (R7)

Scenario: rotate coverage at k=3 is >= the best static single arm under LOO
  Given the outcomes log contains gemma4_e4b s=0..s=2 data for all 5 arms × 17 tasks
  And the best static arm for gemma4_e4b at pass@3 is good_multi_loop (13/17)
  When evaluate_offline_rotate(RuleRouter(), k=3, models=("gemma4_e4b",)) runs under LOO
  Then the reported coverage_rotate is >= 13/17
  And the reported coverage_rotate is <= ceiling_all_arms_union (15/17)
  And the per-model report carries arms_used_count showing >= 2 distinct arms were dispatched across tasks

Scenario: rotate consumes sample slots in order and falls back when a slot is missing
  Given an outcomes log where (gemma4_e4b, sympy__sympy-15017, good_multi_loop) has s=0 resolved=False and no s=1 row
  When evaluate_offline_rotate processes sympy__sympy-15017 at sample_idx=1
  And select_arm_for_sample returns good_multi_loop a second time (after a hypothetical earlier failure)
  Then the simulator falls back to sample s=0's outcome
  And unmet_samples counter records the gap
  And the simulation does NOT raise

Scenario: LOO safety in rotate simulation
  Given evaluate_offline_rotate runs with KNNRouter and held-out iid sympy__sympy-15017
  When KNNRouter.select_arm_for_sample is consulted at each sample
  Then no row with iid="sympy__sympy-15017" enters the router's score computation (exclude_iid honored)
  And the in-trial tried_arms_results only contains in-simulation samples for sympy__sympy-15017
```

**Spec Source**: [bdd-specs.md Feature 5](../2026-05-27-agentbook-outcome-loop-design/bdd-specs.md).

## Files to Modify/Create

- Modify: `experiments/agentbook-ab/pipeline/tests/test_router.py` — append 3 new tests (`test_offline_rotate_coverage_meets_or_exceeds_best_static`, `test_offline_rotate_falls_back_when_sample_slot_missing`, `test_offline_rotate_loo_safety_for_knn`).

## Steps

### Step 1: Verify scenarios are present in the design
- Quote each scenario's `Then` clauses in the test docstring.

### Step 2: Build fixtures
- Synthetic outcomes log with the documented gemma4_e4b 5-arm × 17-task × s=0..s=2 distribution where best static = `good_multi_loop` (13/17), union ceiling = 15/17.
- For the fallback test: an outcomes log where `(gemma4_e4b, sympy__sympy-15017, good_multi_loop, s=0)` is present (resolved=False) and `s=1` is missing entirely.
- For the LOO safety test: a spy that records every row passed into `KNNRouter`'s score computation.

### Step 3: Add the 3 tests (Red)
- **`test_offline_rotate_coverage_meets_or_exceeds_best_static`**: `evaluate_offline_rotate(RuleRouter(), k=3, models=("gemma4_e4b",))` → assert `coverage_rotate >= 13/17` AND `coverage_rotate <= 15/17` AND `arms_used_count >= 2`.
- **`test_offline_rotate_falls_back_when_sample_slot_missing`**: simulator processes `sympy__sympy-15017` at `sample_idx=1` where `select_arm_for_sample` returns `good_multi_loop`; assert it falls back to `s=0`'s outcome; assert `unmet_samples` counter is incremented; assert no exception raised.
- **`test_offline_rotate_loo_safety_for_knn`**: simulator runs with `KNNRouter` and held-out iid `sympy__sympy-15017`; assert no row with `iid="sympy__sympy-15017"` enters the KNN score computation; assert `tried_arms_results` only carries in-simulation samples.

### Step 4: Confirm Red status
- `AttributeError: module 'pipeline.router' has no attribute 'evaluate_offline_rotate'` is the expected failure shape.

## Verification Commands

```bash
# Run the offline-simulator tests — expect Red
cd experiments/agentbook-ab && \
  uv run python -m pytest pipeline/tests/test_router.py -q -k "offline_rotate"

# Confirm prior router tests still pass
cd experiments/agentbook-ab && \
  uv run python -m pytest pipeline/tests/test_router.py -q -k "not offline_rotate"

# Wall-time budget
cd experiments/agentbook-ab && time uv run python -m pytest pipeline/tests/test_router.py -q
```

## Success Criteria

- Exactly 3 new test functions appended to `pipeline/tests/test_router.py`.
- All 3 FAIL Red (`AttributeError` for missing `evaluate_offline_rotate`).
- Prior 6 router tests still pass.
- Per-test wall time < 100 ms.
- Test docstrings reference Feature 5 scenarios by name.
- No new external Python dependencies.
