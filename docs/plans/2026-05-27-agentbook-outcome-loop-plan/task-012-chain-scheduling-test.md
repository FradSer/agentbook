# Task 012: Serial-within-chain scheduling test (Feature 4 scenario 8 / R6)

**depends-on**: task-011

## Description

Add the Red test for the orchestrator's per-`(iid, model)` chain scheduling of `good_rotate` cells. The test creates `experiments/agentbook-ab/pipeline/tests/test_orchestrator.py` with one scenario: when the orchestrator enumerates 3 `good_rotate` cells for `(sympy__sympy-15017, gemma4:e4b)` at `sample_idx=0/1/2`, sample N+1 starts only after sample N's `result.json` has been written; other tasks' chains may execute in parallel; no two cells in the SAME chain ever overlap in wall time. Test MUST fail Red.

The assertion uses spying on `run_cell` to record start/end timestamps and verifies the no-overlap invariant for cells in the same `(iid, model)` chain.

## Execution Context

**Task Number**: 012 of 016
**Phase**: Batch 3 — Adaptive Sample Rotation (RED, orchestrator)
**Prerequisites**:
- task-011 complete: `good_rotate` arm branch in place.

## BDD Scenario

```gherkin
Feature: select_arm_for_sample rotates arms across samples within a task

Scenario: Orchestrator schedules good_rotate samples serially within (iid, model) chain (R6)
  Given the orchestrator enumerates 3 good_rotate cells for (sympy__sympy-15017, gemma4:e4b) at sample_idx=0/1/2
  And the run_chain function dispatches them as a single chain
  When the chain executes under args.workers=12
  Then sample_idx=1 starts only after sample_idx=0's result.json has been written to runs_v2/
  And sample_idx=2 starts only after sample_idx=1's result.json has been written
  And other tasks' chains may execute in parallel (chain-level parallelism preserved)
  And no two cells in the SAME chain ever overlap in wall time
```

**Spec Source**: [bdd-specs.md Feature 4 scenario 8](../2026-05-27-agentbook-outcome-loop-design/bdd-specs.md).

## Files to Modify/Create

- Create: `experiments/agentbook-ab/pipeline/tests/test_orchestrator.py` — single Red test `test_good_rotate_chain_runs_serial_within_chain`.

## Steps

### Step 1: Verify scenario presence in bdd-specs.md
- Quote the scenario verbatim in the test docstring.

### Step 2: Build the fixture
- Stub `run_cell` with a thread-safe recorder that captures `(iid, model, sample_idx, start_ts, end_ts)` and sleeps for a small bounded delay (e.g. 50 ms) to make overlap detectable. The stub also writes a synthetic `result.json` so `_load_prior_sample_outcomes` finds it.
- Enumerate `good_rotate` cells for two `(iid, model)` pairs at three sample indices each.
- Invoke the orchestrator's per-`(iid, model)` chain dispatcher (the symbol does not yet exist — that's exactly what makes the test Red).

### Step 3: Add the Red test
- Run with `args.workers=12` and ≥ 2 chains.
- Assert: for each chain, the start timestamps are monotonically increasing with `sample_idx`; for each `(iid, model)` chain, no two cells' `[start_ts, end_ts]` intervals overlap.
- Assert: across chains, at least two cells from different chains DO overlap in wall time (chain-level parallelism is preserved).

### Step 4: Confirm Red status
- Expected: `ImportError` or `AttributeError` on the chain-dispatcher symbol that does not exist; or, if a flat pool is used, the in-chain interval-overlap assertion fails.

## Verification Commands

```bash
# Run the new orchestrator test — expect Red
cd experiments/agentbook-ab && \
  uv run python -m pytest pipeline/tests/test_orchestrator.py -q

# Confirm sibling tests still pass
cd experiments/agentbook-ab && \
  uv run python -m pytest --ignore=pipeline/tests/test_orchestrator.py -q
```

## Success Criteria

- Exactly 1 new test function in `pipeline/tests/test_orchestrator.py`.
- Test FAILS Red (`ImportError`/`AttributeError` on the chain symbol or the no-overlap assertion).
- Test wall time < 200 ms (sleep delay × number of cells, bounded).
- Test docstring quotes the scenario from bdd-specs.md.
- No other test file regresses.
- No new external Python dependencies.
