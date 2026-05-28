# Task 016: Batch 3 exit gate (offline + online good_rotate sweep)

**depends-on**: task-013, task-015

## Description

Operator-run measurement task that closes Batch 3. Run the offline `evaluate_offline_rotate` simulator against the post-Batch-2 outcomes log to confirm Batch 3 entry-gate condition 3 (`coverage_rotate > coverage_best_static_arm` by ≥ 1 task under LOO); then run an online `good_rotate` sweep against the 17-task gemma4_e4b suite; archive results to `runs_v2.batch3/`; write `runs_v2.batch3/SUMMARY.md` with the 3 exit-gate measurements per [batching-strategy.md "Batch 3"](../2026-05-27-agentbook-outcome-loop-design/batching-strategy.md).

This is an ops/measurement task — no BDD scenario. It is the final task in the plan.

## Execution Context

**Task Number**: 016 of 016
**Phase**: Batch 3 — Exit gate (OPS)
**Prerequisites**:
- task-013 complete (orchestrator chain scheduling); task-015 complete (offline simulator).
- Batch 2 exit gate PASSED and post-Batch-2 outcomes log carries ≥ 1 iid with mixed `resolved` across runtime arms.
- `runs_v2/` empty; current archive is `runs_v2.batch2/`.

## BDD Scenario

```gherkin
# Ops/measurement task — no Gherkin scenario in bdd-specs.md.
# Covered under _index.md "Tasks without direct BDD mapping" per PLAN-BDD-03.
# Acceptance is the operator-readable runs_v2.batch3/SUMMARY.md showing the 3
# exit-gate rows below resolved against the thresholds from batching-strategy.md
# "Batch 3 — Adaptive Sample Rotation".
```

**Spec Source**: [batching-strategy.md "Batch 3 — Adaptive Sample Rotation"](../2026-05-27-agentbook-outcome-loop-design/batching-strategy.md).

## Files to Modify/Create

- Create: `experiments/agentbook-ab/runs_v2.batch3/SUMMARY.md`.
- Read-only: `_oracle/outcomes_log.json`, `runs_v2.batch3/<cell-dirs>/`.

## Steps

### Step 1: Re-confirm Batch 3 entry gates
- Entry gate 1: Batch 2 exit gate passed (verify against `runs_v2.batch2/SUMMARY.md`).
- Entry gate 2: post-Batch-2 outcomes log has ≥ 1 iid where two or more runtime arms differ on `resolved` for the same `(iid, model_slug)`. Compute and record.
- Entry gate 3 (this task's first concrete step): run the offline simulator: `uv run python -m pipeline.router | tee /tmp/router-pre-batch3-report.txt`. Confirm `coverage_rotate > coverage_best_static_arm` by ≥ 1 task under LOO on the post-Batch-2 log. If not, **stop**: record "Batch 3 deferred — entry gate 3 missed" and exit. Surviving Batches 0-2 are a complete shippable result.

### Step 2: Run the online `good_rotate` sweep
- `cd experiments/agentbook-ab && uv run python -m pipeline.orchestrator --arms good_rotate -k 3` against the 17 hard sympy tasks for gemma4_e4b.
- Workers default; the chain scheduler enforces serial-within-chain automatically.
- `mv runs_v2 runs_v2.batch3`.

### Step 3: Refresh outcomes log
- `cd experiments/agentbook-ab && uv run python -m pipeline.router` regenerates `_oracle/outcomes_log.json` from `runs_v2.batch3/` (and prior archives, which the bootstrap harvest extension from task-013 should pick up).

### Step 4: Compute the 3 exit-gate measurements
- **Gate 1** — Unit tests: all rotation tests pass — 6 from task-008 (`pipeline/tests/test_router.py`, Feature 4 scenarios 1-6) + 3 from task-014 (offline-eval Feature 5 scenarios in the same file) + 1 from task-010 (`pipeline/tests/test_arm_context.py`, Feature 4 scenario 7) + 1 from task-012 (`pipeline/tests/test_orchestrator.py`, Feature 4 scenario 8) = 11 new pipeline/tests; PLUS the wider experiment-wide pytest suite stays green. Run `uv run python -m pytest experiments/agentbook-ab/ -q`.
- **Gate 2** — Online lift: `K_rotate ≥ K_best_static_arm` on the post-Batch-2 task set. `K_rotate = |{iid : ∃ sample ∈ good_rotate cells, resolved=True}|`. `K_best_static_arm` is the highest single-arm pass@3 on the post-Batch-2 outcomes log (typically `good_multi_loop`).
- **Gate 3** — No regression: `regression_count == 0` against the post-Batch-2 baseline. Any task resolved under any arm in `runs_v2.batch2/` must still be resolved under some arm (including `good_rotate`) in `runs_v2.batch3/`.

### Step 5: Compute summary signals
- `arms_used_count` distribution across the 17 tasks under `good_rotate`. If a single arm dominates (e.g. one arm dispatched on ≥ 14/17), rotation is degenerating into a static pick; flag for next-iteration review.
- Per-task `rotate_tried_history` summary. Tasks that hit BURN_REPLAY (every runtime arm failed) are candidates for the next Batch 2 cue-refinement pass.
- Final overall picture: `K_post_batch3 / 17` and `(K_post_batch3 − K_pre) / (17 − K_pre)` — the closing measurement on the design's 15/17 → 17/17 lift goal.

### Step 6: Write `runs_v2.batch3/SUMMARY.md`
- 3-row exit-gate table with PASS/FAIL.
- Summary-signals subsections.
- Final paragraph: explicit closing statement on the 15/17 → 17/17 lift goal — "Goal met" with the K trajectory, "Partial lift" with the delta + recommended next iteration, or "Lift did not materialise" with the diagnostic from the summary signals.

### Step 7: Commit Batch 3
- One commit covering tasks 008-016 plus archive metadata.

## Verification Commands

```bash
# Entry gate 3 — offline simulator confirms expected lift
cd experiments/agentbook-ab && \
  uv run python -m pipeline.router | tee /tmp/router-pre-batch3-report.txt

# Online sweep
cd experiments/agentbook-ab && \
  uv run python -m pipeline.orchestrator --arms good_rotate -k 3
mv experiments/agentbook-ab/runs_v2 experiments/agentbook-ab/runs_v2.batch3

# Refresh outcomes log
cd experiments/agentbook-ab && uv run python -m pipeline.router

# Gate 1
cd experiments/agentbook-ab && uv run python -m pytest -q

# K_rotate computation
cd experiments/agentbook-ab && \
  uv run python -m pipeline.router --report 2>/dev/null | tee /tmp/batch3-router-report.txt
```

## Success Criteria

- `runs_v2.batch3/SUMMARY.md` exists with all 3 gate rows resolved (PASS/FAIL).
- Closing statement on the 15/17 → 17/17 goal is unambiguous.
- `regression_count == 0` (Gate 3).
- `K_rotate ≥ K_best_static_arm` (Gate 2) on the post-Batch-2 task set.
- All 36+ unit tests across `experiments/agentbook-ab/` pass at this point.
- Batch 3 lands as its own commit.
- If entry gate 3 missed: the summary explicitly records "Batch 3 deferred" and the plan exits with surviving Batches 0-2 as the shippable result.
