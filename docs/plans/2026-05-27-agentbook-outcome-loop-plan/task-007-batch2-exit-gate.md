# Task 007: Batch 2 exit gate (refined-iid re-eval + regression sweep)

**depends-on**: task-006

## Description

Operator-run measurement task that closes Batch 2. Run `refine_from_outcomes` for real (Opus calls), re-eval the refined iids and the full 17-task suite for regression, archive to `runs_v2.batch2/`, and write `runs_v2.batch2/SUMMARY.md` with the 5 exit-gate measurements per [batching-strategy.md "Batch 2"](../2026-05-27-agentbook-outcome-loop-design/batching-strategy.md). Decide whether Batch 3's entry gate (mixed-outcome surface for rotation to act on) is met.

This is an ops/measurement task — no BDD scenario. Its key output is the **stuck-task recovery rate** `(K_post − K_pre) / (17 − K_pre)` ≥ 0.25, with `regression_count == 0` as a HARD gate.

## Execution Context

**Task Number**: 007 of 016
**Phase**: Batch 2 — Exit gate (OPS)
**Prerequisites**:
- task-006 complete; refinement pytest green.
- `K_pre` recorded in `runs_v2.batch1/SUMMARY.md`.
- Local Opus access via `claude` CLI; budget for ≤ 10 × 60s refinement calls (`--max-tasks 10`, `--workers 2`).
- `runs_v2/` empty; current archive is `runs_v2.batch1/`.

## BDD Scenario

```gherkin
# Ops/measurement task — no Gherkin scenario in bdd-specs.md.
# Covered under _index.md "Tasks without direct BDD mapping" per PLAN-BDD-03.
# Acceptance is the operator-readable runs_v2.batch2/SUMMARY.md showing the 5
# gate rows below resolved against the thresholds from batching-strategy.md
# "Batch 2 — Outcome-Driven Cue Refinement".
```

**Spec Source**: [batching-strategy.md "Batch 2 — Outcome-Driven Cue Refinement"](../2026-05-27-agentbook-outcome-loop-design/batching-strategy.md), [best-practices.md "Comparison protocol"](../2026-05-27-agentbook-outcome-loop-design/best-practices.md).

## Files to Modify/Create

- Create: `experiments/agentbook-ab/runs_v2.batch2/SUMMARY.md`.
- Modify (transient): `_oracle/synth_cache.json` — refinement appends new `revisions[]` entries; top-level aliases advance only when `--require-no-regression` passes.
- Read-only: `_oracle/outcomes_log.json`, `runs_v2.batch2/<cell-dirs>/`.

## Steps

### Step 1: Confirm Batch 2 entry gate
- From `runs_v2.batch1/SUMMARY.md`, confirm Batch 1 PASSED.
- Run `select_stuck(model_slug="gemma4_e4b", min_failure_count=3)` against the current `_oracle/outcomes_log.json`. If empty → Batch 1 already solved everything → close the plan early with "Batch 2 deferred; nothing to refine".
- Record `K_pre` explicitly so the recovery-rate denominator is unambiguous.

### Step 2: Run refinement (Opus calls)
- `cd experiments/agentbook-ab && uv run python -m memory.refine_from_outcomes --min-failure-count 3 --workers 2 --max-tasks 10 --require-no-regression`.
- Log goes to stdout + `refine_from_outcomes.log`.
- Per the comparison protocol: refinement runs OFFLINE (no eval in flight). Do not start an eval concurrently.

### Step 3: (Optional) refresh verifications
- For each refined iid: `uv run python -m memory.extract_verification --redo --only <iid>`. The design notes this is required only when refined `verification_method` text changes significantly.

### Step 4: Re-eval refined iids and full regression sweep
- Refined-iids first (cheaper signal):
  `uv run python -m pipeline.orchestrator --only <refined_iids...> --arms good good_synth good_loop good_multi_loop -k 3`.
- Then full 17-task regression sweep:
  `uv run python -m pipeline.orchestrator --arms good good_synth good_loop good_multi_loop -k 3`.
- Archive: `mv runs_v2 runs_v2.batch2`.

### Step 5: Refresh outcomes log
- `uv run python -m pipeline.router` regenerates `_oracle/outcomes_log.json` from `runs_v2.batch2/`.

### Step 6: Compute the 5 gate measurements
- All numbers read from the refreshed `_oracle/outcomes_log.json`.
- **Gate 1** — Unit tests: `uv run python -m pytest experiments/agentbook-ab/ -q`; all green (15 + 11 search-replace + 10 refinement = 36 plus everything else).
- **Gate 2** — Leak audit: `jq '[.[] | select(.revisions) | .revisions[-1].leak_lines_removed]' _oracle/synth_cache.json`. Expect ≥ 80% of refined entries `== 0`; any value ≥ 3 triggers a prompt audit before merging.
- **Gate 3** — Regression (HARD): `regression_count == 0`. `refine_from_outcomes.py --require-no-regression` was on; confirm it exited 0 and top-level aliases advanced.
- **Gate 4** — Stuck-task recovery: `K_post = |{iid : ∃ arm, ∃ sample, resolved=True}|`. Compute `(K_post − K_pre) / (17 − K_pre) ≥ 0.25`.
- **Gate 5** — Cost telemetry: median `elapsed_s` per revision ≤ 60s; total Opus wall time + request count logged.

### Step 7: Compute optimization signals
- For each refined iid, the diff between `revisions[0].localization_cues` and `revisions[1].localization_cues`. Cluster the edits — "enumerated call sites", "added precondition", "narrowed pattern" — and note which cluster correlates with recovery.
- `failure_evidence_count` vs recovery outcome.
- Which arm now resolves each refined task (informs Batch 3 rotation weights).

### Step 8: Write `runs_v2.batch2/SUMMARY.md`
- Mandatory table from [best-practices.md "Comparison protocol"](../2026-05-27-agentbook-outcome-loop-design/best-practices.md): `K_pre`, `K_post`, Absolute `K_post/17`, Stuck-task recovery rate, `K_per_arm_post`, `regression_count`.
- 5-row exit-gate table with PASS/FAIL.
- Optimization-signals subsections.
- Final paragraph: decision — "Advance to Batch 3" only when (a) all 5 gates PASS, (b) post-Batch-2 log has ≥ 1 iid with mixed `resolved` across runtime arms, and (c) Batch 3 entry-gate condition 3 (offline `evaluate_offline_rotate > coverage_best_static_arm`) — but condition 3 cannot be measured yet because the simulator does not exist; defer condition 3 verification to task-016. Default decision text: "Advance to Batch 3, pending offline-simulator confirmation in task-016."

### Step 9: Commit Batch 2
- One commit covering task-005, task-006, task-007 changes plus archive metadata + `_oracle/synth_cache.json` revision append.

## Verification Commands

```bash
# Refinement (real Opus calls)
cd experiments/agentbook-ab && \
  uv run python -m memory.refine_from_outcomes --min-failure-count 3 --workers 2 --max-tasks 10 \
    | tee refine_from_outcomes.log

# Refined-iid re-eval
cd experiments/agentbook-ab && \
  uv run python -m pipeline.orchestrator --only <REFINED_IIDS> \
    --arms good good_synth good_loop good_multi_loop -k 3

# Full regression sweep
cd experiments/agentbook-ab && \
  uv run python -m pipeline.orchestrator \
    --arms good good_synth good_loop good_multi_loop -k 3
mv experiments/agentbook-ab/runs_v2 experiments/agentbook-ab/runs_v2.batch2

# Gate 1
cd experiments/agentbook-ab && uv run python -m pytest -q

# Leak audit (Gate 2)
jq '[.[] | select(.revisions) | .revisions[-1].leak_lines_removed]' \
  experiments/agentbook-ab/_oracle/synth_cache.json

# K_post (Gate 4)
cd experiments/agentbook-ab && uv run python -m pipeline.router --report
```

## Success Criteria

- `runs_v2.batch2/SUMMARY.md` exists with all 5 gate rows resolved + comparison-protocol table.
- `regression_count == 0` (HARD gate).
- Stuck-task recovery rate ≥ 0.25 OR the summary records the failure mode with explicit "stop and root-cause" rather than advancing.
- Leak audit: ≥ 80% of refined entries have `leak_lines_removed == 0`; any audit at ≥ 3 documented.
- `_oracle/outcomes_log.json` refreshed and pinned.
- Top-level aliases on every refined iid advanced (per `--require-no-regression` clean exit).
- Batch 2 lands as its own commit.
- If Gate 4 misses (recovery < 0.25): summary explicitly says "Do not proceed to Batch 3" and the plan exits without task-008+.
