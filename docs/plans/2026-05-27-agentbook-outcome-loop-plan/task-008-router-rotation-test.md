# Task 008: select_arm_for_sample router tests (Feature 4 scenarios 1-6)

**depends-on**: task-007

## Description

Add the router-level Red tests for `select_arm_for_sample` on both `RuleRouter` and `KNNRouter`. Create `experiments/agentbook-ab/pipeline/tests/__init__.py` and `experiments/agentbook-ab/pipeline/tests/test_router.py` with 6 tests covering Feature 4 scenarios 1-6: FRESH_ARM at sample 0, FRESH_ARM after failure, REPLAY_WIN, BURN_REPLAY, Rule/KNN disagreement at sample 1, and existing `select_arms` signature backwards-compat. All new tests MUST fail Red.

These tests are pure router unit tests — no orchestrator, no `arm_context`, no filesystem-coupled `good_rotate` arm. Stdlib + in-memory fixtures only.

## Execution Context

**Task Number**: 008 of 016
**Phase**: Batch 3 — Adaptive Sample Rotation (RED, router core)
**Prerequisites**:
- task-007 complete; Batch 2 exit gate passed AND post-Batch-2 outcomes log contains ≥ 1 iid with mixed `resolved` across runtime arms.
- `_oracle/outcomes_log.json` reflects the Batch 2 refined state.

## BDD Scenario

```gherkin
Feature: select_arm_for_sample rotates arms across samples within a task

Background:
  Given RUNTIME_ARMS is ("good", "good_synth", "good_loop", "good_multi_loop")
  And the outcomes log records (model_slug, iid, arm, sample_idx, resolved)
  And LOO exclusion of the held-out iid is honored for KNNRouter

Scenario: First sample picks the router's top-ranked arm (FRESH_ARM, empty history)
  Given a RuleRouter and multisite gemma features
  When select_arm_for_sample(features, "gemma4_e4b", sample_idx=0, tried_arms_results={}) is called
  Then it returns "good_multi_loop" (rule's top pick for multisite gemma)

Scenario: After a failed top pick, sample 1 advances to rank-2 (FRESH_ARM after failure)
  Given a RuleRouter, multisite gemma features
  And tried_arms_results = {"good_multi_loop": [False]}
  When select_arm_for_sample(..., sample_idx=1, tried_arms_results=...) is called
  Then the returned arm is NOT "good_multi_loop"
  And the returned arm is the next-best by rule ranking among RUNTIME_ARMS
  And the returned arm is in RUNTIME_ARMS

Scenario: A prior win short-circuits to REPLAY_WIN
  Given tried_arms_results = {"good_multi_loop": [False], "good_loop": [True]}
  When select_arm_for_sample(..., sample_idx=2, tried_arms_results=...) is called
  Then it returns "good_loop"

Scenario: All RUNTIME_ARMS tried, all failed -- BURN_REPLAY returns the top-ranked arm
  Given a KNNRouter and tried_arms_results that records resolved=False for every arm in RUNTIME_ARMS
  When select_arm_for_sample(features, "gemma4_e4b", sample_idx=4, tried_arms_results=..., exclude_iid="sympy__sympy-15017") is called
  Then it returns ranking[0]
  And the returned arm is in RUNTIME_ARMS

Scenario: Rule and KNN disagree on the fresh arm at sample 1
  Given multisite gemma features, tried_arms_results = {"good_multi_loop": [False]}
  When RuleRouter.select_arm_for_sample is called
  Then it returns "good_loop" (rule's #2 for multisite)
  When KNNRouter.select_arm_for_sample is called against an outcomes log where
    "good" resolves 3/3 nearest neighbours and "good_loop" resolves 1/3
  Then it returns "good"

Scenario: Existing select_arms callers are unaffected (no signature change)
  Given existing call sites use select_arms(iid, model_slug, k=1)
  When the new select_arm_for_sample method is shipped
  Then no caller of select_arms breaks
  And select_arms returns the same arm it returned before this change
```

**Spec Source**: [bdd-specs.md Feature 4 scenarios 1-6](../2026-05-27-agentbook-outcome-loop-design/bdd-specs.md).

## Files to Modify/Create

- Create: `experiments/agentbook-ab/pipeline/tests/__init__.py` (empty file).
- Create: `experiments/agentbook-ab/pipeline/tests/test_router.py` — 6 tests covering Feature 4 scenarios 1-6. Test functions named after the scenarios (e.g. `test_fresh_arm_at_sample0`, `test_fresh_arm_after_failure`, `test_replay_win`, `test_burn_replay_when_all_tried`, `test_rule_vs_knn_disagreement_at_sample_1`, `test_select_arms_signature_unchanged`).

## Steps

### Step 1: Verify scenarios are present in the design
- bdd-specs.md Feature 4 carries scenarios 1-6 verbatim above.

### Step 2: Build fixtures
- Multisite gemma feature dict (use the canonical fixture from existing `pipeline.router` callers; the rule for multisite gemma is well-defined in `RuleRouter`).
- Synthetic outcomes log for the KNN-disagreement test: feed 3 nearest-neighbour iids where `good` resolves 3/3 and `good_loop` resolves 1/3 for `gemma4_e4b`.
- Helper to call `select_arms(iid="X", model_slug="gemma4_e4b", k=1)` and capture the prior return for the signature-backcompat test (regression fixture).

### Step 3: Add the 6 tests (Red)
- **`test_fresh_arm_at_sample0`**: empty `tried_arms_results` → returns `"good_multi_loop"` (RuleRouter's top pick).
- **`test_fresh_arm_after_failure`**: `tried_arms_results={"good_multi_loop":[False]}` → returns rule's rank-2 arm; asserts return is in `RUNTIME_ARMS` and is NOT `"good_multi_loop"`.
- **`test_replay_win`**: `tried_arms_results={"good_multi_loop":[False], "good_loop":[True]}` → returns `"good_loop"` (REPLAY_WIN short-circuits).
- **`test_burn_replay_when_all_tried`**: KNNRouter, all 4 arms have `[False]`, `exclude_iid="sympy__sympy-15017"` → returns `ranking[0]`; assert return is in `RUNTIME_ARMS`.
- **`test_rule_vs_knn_disagreement_at_sample_1`**: RuleRouter returns `"good_loop"`; KNNRouter against a crafted outcomes log returns `"good"`. Two separate assertions in one test.
- **`test_select_arms_signature_unchanged`**: snapshot the current `select_arms(iid, model_slug, k=1)` return for a known fixture; after `select_arm_for_sample` is added, `select_arms` returns the same value.

### Step 4: Confirm Red status
- Collection error (`AttributeError: 'RuleRouter' object has no attribute 'select_arm_for_sample'`) is the expected failure shape for tests 1-5; test 6 may pass coincidentally and stays green throughout.

## Verification Commands

```bash
# Run the new router tests — expect Red
cd experiments/agentbook-ab && \
  uv run python -m pytest pipeline/tests/test_router.py -q

# Confirm the rest of the suite is still green
cd experiments/agentbook-ab && \
  uv run python -m pytest --ignore=pipeline/tests -q

# Wall-time budget
cd experiments/agentbook-ab && time uv run python -m pytest pipeline/tests/test_router.py -q
```

## Success Criteria

- Exactly 6 new test functions in `pipeline/tests/test_router.py`.
- `pipeline/tests/__init__.py` exists (empty).
- Tests 1-5 FAIL Red (`AttributeError` for missing `select_arm_for_sample`); test 6 (signature-backcompat) may pass and stays green.
- No other test file regresses.
- Per-test wall time < 50 ms (in-memory fixtures only).
- Each test docstring references the scenario name from bdd-specs.md for traceability.
- No new external Python dependencies.
