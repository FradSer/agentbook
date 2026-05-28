# Task 010: good_rotate arm + arm_meta routing record test (Feature 4 scenario 7)

**depends-on**: task-009

## Description

Add a Red test for the `good_rotate` arm branch in `pipeline/arm_context.py`. Test that `build_prompt(iid, "good_rotate", ...)` reads prior sample outcomes from disk, consults `select_arm_for_sample`, delegates to the chosen sub-arm, and stamps the routing decision into `arm_meta` (`routed_from`, `routed_to`, `rotate_sample_idx`, `rotate_tried_history`). The test MUST fail Red. Extend `pipeline/tests/test_router.py` (or add `pipeline/tests/test_arm_context.py`) with the single scenario.

This is the only Feature 4 scenario that exercises the `arm_context` integration; the others are router-level. Use `tmp_path` to stand up a fake `runs_v2/sympy__sympy-15017__good_rotate__gemma4_e4b__s0/result.json` with `arm_meta.routed_to="good_multi_loop"` and `resolved=False`, then run `build_prompt(iid, "good_rotate", ..., sample_idx=1)` and assert the meta fields.

## Execution Context

**Task Number**: 010 of 016
**Phase**: Batch 3 — Adaptive Sample Rotation (RED, arm_context)
**Prerequisites**:
- task-009 complete: `select_arm_for_sample` available on both routers.

## BDD Scenario

```gherkin
Feature: select_arm_for_sample rotates arms across samples within a task

Scenario: good_rotate cell records the routing decision in arm_meta
  Given an orchestrator runs a good_rotate cell at sample_idx=1 for sympy__sympy-15017 on gemma4_e4b
  And the prior sample at sample_idx=0 has a result.json with arm_meta.routed_to="good_multi_loop" and resolved=False
  When build_prompt(iid, "good_rotate", ...) executes
  Then _load_prior_sample_outcomes returns {"good_multi_loop": [False]}
  And select_arm_for_sample is consulted with that history
  And the returned arm_meta carries routed_from="good_rotate", routed_to=<the chosen sub-arm>, rotate_sample_idx=1, rotate_tried_history={"good_multi_loop": [False]}
```

**Spec Source**: [bdd-specs.md Feature 4 scenario 7](../2026-05-27-agentbook-outcome-loop-design/bdd-specs.md).

## Files to Modify/Create

- Create or extend: `experiments/agentbook-ab/pipeline/tests/test_arm_context.py` (new) — single Red test `test_good_rotate_cell_records_arm_meta`. (Alternative placement: extend `pipeline/tests/test_router.py`; the new-file choice keeps the router test file router-only.)

## Steps

### Step 1: Verify scenario presence in bdd-specs.md
- Quote the scenario verbatim in the test docstring.

### Step 2: Build the fixture
- Under `tmp_path`, materialise:
  - `runs_v2/sympy__sympy-15017__good_rotate__gemma4_e4b__s0/result.json` with body `{"resolved": false, "arm_meta": {"routed_to": "good_multi_loop"}}`.
  - Minimal `_oracle/synth_cache.json` containing an entry for `"sympy__sympy-15017"` so `extract_features` and `_synth_entry` succeed.
- Monkeypatch the module-level paths (`SYNTH_CACHE`, runs root) to point at the fixture.

### Step 3: Add the Red test
- Call `build_prompt("sympy__sympy-15017", "good_rotate", client=stub_client, model_slug="gemma4_e4b", sample_idx=1)`.
- Assert that `_load_prior_sample_outcomes` was reached (e.g. via spy or direct call check) and returned `{"good_multi_loop": [False]}`.
- Assert `meta["routed_from"] == "good_rotate"`, `meta["routed_to"]` in `RUNTIME_ARMS` and != `"good_rotate"`, `meta["rotate_sample_idx"] == 1`, `meta["rotate_tried_history"] == {"good_multi_loop": [False]}`.

### Step 4: Confirm Red status
- Expected failure shape: `arm == "good_rotate"` branch does not exist → `build_prompt` raises or returns a no-op stub. Either failure mode is acceptable Red.

## Verification Commands

```bash
# Run the new arm_context test — expect Red
cd experiments/agentbook-ab && \
  uv run python -m pytest pipeline/tests/test_arm_context.py -q

# Confirm sibling router tests still green
cd experiments/agentbook-ab && \
  uv run python -m pytest pipeline/tests/test_router.py -q
```

## Success Criteria

- Exactly 1 new test function in `pipeline/tests/test_arm_context.py`.
- Test FAILS Red (`good_rotate` branch does not exist or `_load_prior_sample_outcomes` is missing).
- No other test file regresses.
- Test wall time < 50 ms.
- Test docstring quotes the scenario name from bdd-specs.md.
- No new external Python dependencies.
