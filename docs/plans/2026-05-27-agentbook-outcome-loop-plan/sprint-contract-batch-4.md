# Batch 4 Sprint Contract

## Tasks

| ID  | Subject | Type |
|-----|---------|------|
| 012 | Serial-within-chain scheduling test (Feature 4 scenario 8 / R6) | test |
| 013 | Orchestrator chain scheduling implementation | impl |
| 014 | evaluate_offline_rotate simulator tests (Feature 5) | test |
| 015 | evaluate_offline_rotate implementation + main() CLI integration | impl |

Two independent Red-Green pairs. Within the coordinator, run them in sequence (012→013, then 014→015) — independence allows interleaving but the dependency graph rules out 015 finishing before 013 starts only in the sense that both consume `select_arm_for_sample` from Batch 3; structural independence between the orchestrator changes (012/013) and the simulator (014/015) means either order works.

**Task 016** (Batch 3 exit gate ops sweep) is operator-deferred outside this batch — same treatment as 004/007.

## Acceptance Criteria

### Task 012: Serial-within-chain scheduling test

- [ ] `experiments/agentbook-ab/pipeline/tests/test_orchestrator.py` exists with 1 test `test_good_rotate_chain_runs_serial_within_chain`.
- [ ] Test fixture: stubbed `run_cell` records `(iid, model, sample_idx, start_ts, end_ts)` and sleeps a small bounded delay (e.g. 50 ms) to make overlap detectable. The stub writes a synthetic `result.json` so `_load_prior_sample_outcomes` finds it.
- [ ] Test enumerates `good_rotate` cells for ≥ 2 distinct `(iid, model)` pairs at 3 sample indices each (so chain-level parallelism can be verified alongside in-chain serial).
- [ ] Test invokes the orchestrator's per-`(iid, model)` chain dispatcher symbol (does not yet exist → Red).
- [ ] Test assertions: (a) start timestamps within each chain are monotonically increasing with `sample_idx`; (b) for each `(iid, model)` chain, no two cells' `[start_ts, end_ts]` intervals overlap; (c) across chains, at least two cells from different chains DO overlap (chain-level parallelism preserved).
- [ ] Test FAILS Red: `ImportError`/`AttributeError` on the chain symbol that does not exist, OR (if a flat pool is used) the in-chain interval-overlap assertion fails.
- [ ] Test wall-time < 200 ms; bounded by sleep delay × cell count.
- [ ] **Red-state confirmation:** `uv run python -m pytest experiments/agentbook-ab/pipeline/tests/test_orchestrator.py -q` reports 1 failure with the structural shape above.

### Task 013: Orchestrator chain scheduling implementation

- [ ] `test_good_rotate_chain_runs_serial_within_chain` PASSES.
- [ ] `pipeline/orchestrator.py` splits scheduling at `main()` after `enumerate_cells`: `rotate_cells = [c for c in todo if c.arm == "good_rotate"]` runs through `run_chain` (serial within `(iid, model)`); `other_cells = [c for c in todo if c.arm != "good_rotate"]` runs through the existing parallel pool.
- [ ] `run_chain(chain: list[Cell], llm, client, ...)` is added; body iterates `chain` in `sample_idx` order calling `run_cell` serially. No `ThreadPoolExecutor` inside the chain.
- [ ] `_has_memory` gate extended with the `good_rotate` case: `c.iid in mem_ids and c.iid in synth_ids and c.iid in loop_ids` (union of all sub-arm prerequisites).
- [ ] `run_cell` passes `cell.sample_idx` to `build_prompt`. If `Cell` does not yet carry `sample_idx`, add it as a dataclass field (verify the existing schema first — CODE-ASSUME-02).
- [ ] `bootstrap_outcomes_log` harvest extended to read archived `runs_v2.*/` directories (e.g. `runs_v2.preflight/`, `runs_v2.batch1/`, etc.) when present so the outcomes log carries full lineage across batches. Skip the active `runs_v2/` only when explicitly excluded.
- [ ] Full code-batch pytest stays green (`harness/tests/` + `memory/tests/` + `pipeline/tests/` = 36 + 6 + 1 + 1 = 44 PASS).
- [ ] Ruff passes on `pipeline/orchestrator.py`.
- [ ] No new external Python dependencies.
- [ ] **Anti-stub:** no placeholder bodies.

### Task 014: evaluate_offline_rotate simulator tests (Feature 5)

- [ ] `experiments/agentbook-ab/pipeline/tests/test_router.py` extended (appended) with 3 new tests: `test_offline_rotate_coverage_meets_or_exceeds_best_static`, `test_offline_rotate_falls_back_when_sample_slot_missing`, `test_offline_rotate_loo_safety_for_knn`.
- [ ] Synthetic outcomes log fixtures: gemma4_e4b 5-arm × 17-task × s=0..s=2 distribution where best static arm = `good_multi_loop` (13/17), union ceiling = 15/17; the second test seeds `(gemma4_e4b, sympy__sympy-15017, good_multi_loop, s=0)` with `resolved=False` and no `s=1` row; the third test wires a spy that records every row passed into `KNNRouter`'s score computation.
- [ ] All 3 tests FAIL Red — `AttributeError: module 'pipeline.router' has no attribute 'evaluate_offline_rotate'` (or equivalent).
- [ ] Per-test wall-time < 100 ms.
- [ ] No real `_oracle/outcomes_log.json` access; pure synthetic fixtures.
- [ ] Test 6 from task-008 plus the 3 new tests = 9 total Feature-4/5 router tests; prior 6 router tests stay green.
- [ ] **Red-state confirmation:** scoped pytest reports the 3 new tests failing with the AttributeError shape.

### Task 015: evaluate_offline_rotate implementation + main() CLI integration

- [ ] All 3 Feature-5 tests in `pipeline/tests/test_router.py` PASS.
- [ ] `evaluate_offline_rotate(router, *, k: int = 3, models: tuple[str, ...] = ("gemma4_e4b",)) -> dict[str, dict]` exists in `pipeline/router.py`. Returns `{model: {coverage_rotate, ceiling_all_arms_union, arms_used_count, unmet_samples}}`.
- [ ] Implementation per architecture.md "evaluate_offline_rotate":
  - For each `(model, iid)`: maintain `tried: dict[str, list[bool]]`, `consume_idx: dict[str, int] = defaultdict(int)`.
  - For `s in range(k)`: pick arm via `router.select_arm_for_sample(features, model, sample_idx=s, tried_arms_results=tried, exclude_iid=iid)` (LOO).
  - Look up `outcomes[(model, iid, arm, consume_idx[arm])]`; on miss, fall back to `s=0` and increment `unmet_samples`.
  - Record into `tried`; increment `consume_idx[arm]`; short-circuit on `resolved == True`.
  - Coverage = tasks with at least one True hit; `ceiling_all_arms_union` from arm-level pass@k (reuse existing `evaluate_offline` utility).
  - `arms_used_count = |{arm in tried.keys() across all iids}|`.
- [ ] `main()` extended with the rotation row: print a third per-router/k combination labeled `rotate` with coverage and `arms_used_count` columns.
- [ ] `_pick_unexplored` reused (not re-implemented).
- [ ] Full code-batch pytest stays green (`harness/tests/` + `memory/tests/` + `pipeline/tests/` = 47 PASS total).
- [ ] Ruff passes on `pipeline/router.py`.
- [ ] No new external Python dependencies.
- [ ] **Anti-stub:** no placeholder bodies.

## Red-Green Pairs

| Test Task | Impl Task | Expected Red State | Expected Green State |
|-----------|-----------|--------------------|----------------------|
| 012 | 013 | 1/1 fails (no chain dispatcher symbol OR in-chain interval overlap) | 1/1 PASS; cumulative 44 PASS |
| 014 | 015 | 3/3 fail (AttributeError on `evaluate_offline_rotate`) | 3/3 PASS; cumulative 47 PASS |

Two independent pairs; sequential within the coordinator (012→013 then 014→015) is the cleanest path.

## Evaluation Criteria Preview

| Item ID | Description |
|---------|-------------|
| CODE-ASSUME-01 | Grep `pipeline/orchestrator.py` for `Cell` dataclass fields, `enumerate_cells`, `run_cell`, `_has_memory`, `bootstrap_outcomes_log` shape before modifying |
| CODE-ASSUME-02 | Confirm `Cell.sample_idx` exists (add it as a dataclass field if missing — verify via grep, do not assume) |
| CODE-EDIT-01 | Re-Read modified files between Edits |
| CODE-LINT-01 | Ruff after each task |
| CODE-TEST-01 | In-memory fixtures only; the chain-scheduling test uses a stub `run_cell` rather than spinning up a real orchestrator-LLM stack |
| CODE-TEST-03 | Red shape is clean AttributeError/missing-symbol/interval-overlap, not incidental fixture errors |
| CODE-VERIFY-01 | Per-task pytest AND scoped regression sweep exit 0 |
| CODE-VERIFY-02 | Touching `pipeline/orchestrator.py` and `pipeline/router.py` (shared infra) re-runs the full code-batch suite |
| CODE-SCOPE-01 | Stay within declared file lists |
| CODE-SCOPE-02 | Commit message names the feature scope |

## Sign-off

- **Generator:** executing-plans
- **Timestamp:** 2026-05-29T01:30:00Z
- **Status:** READY
- **Revision:** 0
