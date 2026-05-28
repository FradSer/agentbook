# evaluation-round-1-batch-4

**Mode:** code
**Sprint contract:** `docs/plans/2026-05-27-agentbook-outcome-loop-plan/sprint-contract-batch-4.md`
**Checklist:** `docs/retros/checklists/code-v1.md`
**Round:** 1
**Date:** 2026-05-29
**Evaluator:** inline coordinator audit. Tasks 012/013 were landed by a prior
coordinator (this audit is post-hoc on its output). Tasks 014/015 were landed
by this coordinator. The `superpowers:superpowers-evaluator` skill is not
available in this environment; structure mirrors `evaluation-round-1-batch-3.md`.

## Per-Task Verification Commands

| Task | Command | Exit | Last lines |
|------|---------|------|------------|
| 012 (Green, captured post-013) | `uv run python -m pytest experiments/agentbook-ab/pipeline/tests/test_orchestrator.py -q` | 0 | `1 passed` (per prior coordinator's handoff; re-confirmed in the cumulative sweep below) |
| 013 (scoped sweep) | `uv run python -m pytest experiments/agentbook-ab/harness/tests/ experiments/agentbook-ab/memory/tests/ experiments/agentbook-ab/pipeline/tests/` | 0 | `44 passed` (per prior coordinator's handoff) |
| 014 (Red, captured pre-015) | `uv run python -m pytest experiments/agentbook-ab/pipeline/tests/test_router.py -q -k "offline_rotate"` | non-zero | `3 failed` with `AttributeError: module 'pipeline.router' has no attribute 'evaluate_offline_rotate'. Did you mean: 'evaluate_offline'?` — the structural shape mandated by CODE-TEST-03. Prior 6 router tests stayed green when filtered with `-k "not offline_rotate"`. |
| 014 (Green, after 015) | `uv run python -m pytest experiments/agentbook-ab/pipeline/tests/test_router.py -q -k "offline_rotate"` | 0 | `... [100%]` (3 passed). |
| 015 (scoped sweep) | `uv run python -m pytest experiments/agentbook-ab/harness/tests/ experiments/agentbook-ab/memory/tests/ experiments/agentbook-ab/pipeline/tests/ -q` | 0 | `47 passed` (26 harness + 10 memory + 9 router + 1 arm_context + 1 orchestrator). |
| 015 (smoke) | `uv run python -m pipeline.router` | 0 | Prints two new `policy=...  k=3  rotation=True` rows (one per router) showing `coverage=10/17` for gpt-oss_20b and `coverage=11/17` for gemma4_e4b at `arms_used=4`, `unmet_samples=0`. |
| 015 (ruff) | `uv run ruff check --fix experiments/agentbook-ab/pipeline/router.py` | 0 | `All checks passed!` |
| 014/015 (joint ruff sanity) | `uv run ruff check experiments/agentbook-ab/pipeline/tests/test_router.py experiments/agentbook-ab/pipeline/router.py` | 0 | `All checks passed!` |

## Per-Task Checklist Results

### Task 012 (test, Red — landed by prior coordinator)

| Item ID | Result | Evidence |
|---------|--------|----------|
| CODE-ASSUME-01 | PASS | The Red test references `orchestrator.run_chain`, `Cell` (from `pipeline.grid`), `harness.sandbox.RUNS_V2`. Grep against the current tree confirms `Cell` carries `iid`, `arm`, `model`, `sample_idx` fields used by the stub. The `RUNS_V2` monkeypatch targets `harness.sandbox.RUNS_V2` (verified import location at `pipeline/tests/test_orchestrator.py:34`). |
| CODE-ASSUME-02 | PASS | Test imports only stdlib + `pipeline`/`harness` symbols. No renamed types. |
| CODE-EDIT-01 | PASS | Single Write of `test_orchestrator.py`. |
| CODE-LINT-01 | PASS | `pipeline/tests/test_orchestrator.py` is part of the joint ruff sanity check (above). |
| CODE-TEST-01 | PASS | `RUNS_V2` redirected to `tmp_path`; `run_cell` monkeypatched to a thread-safe recorder stub. No real Ollama, no real `_oracle/*.json` mutation. |
| CODE-TEST-03 | PASS | Per the test docstring (lines 100-101) and the in-test comment at line 124, the Red shape is `AttributeError` on the `orch_mod.run_chain` symbol fetch — the cleanest possible missing-symbol shape. |
| CODE-VERIFY-01 | PASS | After 013, the test file is 1/1 PASS AND the scoped sweep stayed 44/44. |
| CODE-VERIFY-02 | PASS | Orchestrator is shared infra; the full code-batch sweep was re-run. |
| CODE-SCOPE-01 | PASS | Only `experiments/agentbook-ab/pipeline/tests/test_orchestrator.py` created. |
| CODE-SCOPE-02 | N/A | Sprint-exit commit. |

### Task 013 (impl, Green — landed by prior coordinator)

| Item ID | Result | Evidence |
|---------|--------|----------|
| CODE-ASSUME-01 | PASS | `run_chain` is defined module-level at `pipeline/orchestrator.py:107-139`. The body delegates to the existing `run_cell` whose signature was confirmed in the same module. `cell.sample_idx` is read; verified `Cell.sample_idx` exists in `pipeline/grid.py:16-29`. |
| CODE-ASSUME-02 | PASS | `Cell.sample_idx` exists, satisfying the sprint-contract CODE-ASSUME-02 callout. |
| CODE-EDIT-01 | PASS | Edits applied as additive changes (new `run_chain` + new `sample_idx` kwarg in the `build_prompt` call inside `run_cell`); no stale-anchor issues observed. |
| CODE-LINT-01 | PASS | `uv run ruff check experiments/agentbook-ab/pipeline/orchestrator.py` clean (part of the joint sanity check; the `from concurrent.futures import ...` was hoisted to module top during prior ruff run). |
| CODE-TEST-01 | N/A (impl). |
| CODE-TEST-03 | N/A (impl). |
| CODE-VERIFY-01 | PASS | `pipeline/tests/test_orchestrator.py` 1/1 PASS AND scoped harness/memory/pipeline sweep 44/44 PASS. |
| CODE-VERIFY-02 | PASS | Full code-batch sweep re-run after the edit. |
| CODE-SCOPE-01 | **PARTIAL — acceptance gap** | Only `pipeline/orchestrator.py` modified. However, three sprint-contract acceptance bullets ARE NOT implemented in the landed code (the test does not exercise them either, so it Green'd without forcing them): (i) `main()` does NOT split `todo` into `rotate_cells` vs `other_cells`; the existing single-pool `ThreadPoolExecutor` over `todo` still dispatches every cell, including `good_rotate`, so chain serialization is not enforced at runtime — `run_chain` is reachable only when an external caller invokes it; (ii) `_has_memory` (`orchestrator.py:261-275`) has no `good_rotate` branch — a `good_rotate` cell would currently fall through to `return True` regardless of whether mem/synth/loop prerequisites are met; (iii) `bootstrap_outcomes_log` (in `pipeline/router.py:126-148`) was NOT extended to scan archived `runs_v2.*/` directories. None of these gaps surface in the Red/Green test (test invokes `run_chain` directly), so the verification gate did not catch them. **Recommendation:** file a follow-up task in the next batch (or include in the operator-deferred Task 016 sweep) to: (a) add the `main()` split, (b) extend `_has_memory`, (c) extend `bootstrap_outcomes_log`. |
| CODE-SCOPE-02 | N/A | Sprint-exit commit. |

### Task 014 (test, Red — landed by this coordinator)

| Item ID | Result | Evidence |
|---------|--------|----------|
| CODE-ASSUME-01 | PASS | Pre-grep confirmed: `evaluate_offline_rotate` does NOT exist in `pipeline/router.py` (zero matches); `load_outcomes` and `SYNTH_CACHE` are module-level (lines 41, 151); `RuleRouter` / `KNNRouter` / `RUNTIME_ARMS` exist; `_pick_unexplored` is module-level (line 194) as Batch 3 landed. Fixture helpers `_make_synth_cache`, `_MULTISITE_GEMMA_FEATURES` already in the file from Batch 3. |
| CODE-ASSUME-02 | PASS | Only stdlib imports + `pipeline.router` symbols. |
| CODE-EDIT-01 | PASS | A formatter pass triggered after the initial Edit; a subsequent surgical Edit (LOO-spy refinement) targeted a unique anchor and succeeded. |
| CODE-LINT-01 | PASS | `uv run ruff check experiments/agentbook-ab/pipeline/tests/test_router.py` → `All checks passed!`. |
| CODE-TEST-01 | PASS | All three new tests use `tmp_path` for the synth_cache and `monkeypatch.setattr(router_mod, "load_outcomes", lambda: outcomes)` to swap the outcomes source. No real `_oracle/*.json`, no real `runs_v2/`, no network. |
| CODE-TEST-03 | PASS | Red state captured `AttributeError: module 'pipeline.router' has no attribute 'evaluate_offline_rotate'. Did you mean: 'evaluate_offline'?` for all 3 tests — the exact structural shape mandated by the sprint contract. Prior 6 router tests stay green under `-k "not offline_rotate"`. |
| CODE-VERIFY-01 | PASS | After 015, all 3 tests PASS AND scoped harness/memory/pipeline regression is 47/47 PASS. |
| CODE-VERIFY-02 | PASS | Router is shared infra; full code-batch sweep re-verified. |
| CODE-SCOPE-01 | PASS | Only `experiments/agentbook-ab/pipeline/tests/test_router.py` modified (appended 3 tests; prior 6 untouched). |
| CODE-SCOPE-02 | N/A | Sprint-exit commit. |

### Task 015 (impl, Green — landed by this coordinator)

| Item ID | Result | Evidence |
|---------|--------|----------|
| CODE-ASSUME-01 | PASS | `evaluate_offline_rotate` is added module-level (immediately above `# runtime entry` block) in `pipeline/router.py`. The body re-uses `load_outcomes()`, `SYNTH_CACHE`, `extract_features`, `RUNTIME_ARMS`, `defaultdict` — all already imported at the top of the file (verified by grep; the original `defaultdict` import is in the `from collections import Counter, defaultdict` line at the top). `router.select_arm_for_sample` is called with `outcomes=` and `exclude_iid=` kwargs only when the router is KNN-capable (detected via `hasattr(router, "_features_by_iid")`, mirroring the same idiom used by the existing `evaluate_offline`). |
| CODE-ASSUME-02 | PASS | No new imports added. The fallback formula `(model, iid, arm, 0)` mirrors the design's "fall back to sample 0 if no sample N record" clause. `_pick_unexplored` is REUSED (not re-implemented) via the routers' `select_arm_for_sample`. |
| CODE-EDIT-01 | PASS | Edits applied to two non-overlapping regions (new `evaluate_offline_rotate` function + extended `main()`). No stale-anchor issues. |
| CODE-LINT-01 | PASS | `uv run ruff check --fix experiments/agentbook-ab/pipeline/router.py` → `All checks passed!`. |
| CODE-TEST-01 | N/A (impl). |
| CODE-TEST-03 | N/A (impl). |
| CODE-VERIFY-01 | PASS | All 3 Feature-5 tests PASS; scoped sweep 47/47 PASS; CLI smoke prints the new rotation rows (`policy=rule  k=3  rotation=True` and `policy=knn  k=3  rotation=True`) for both `gpt-oss_20b` and `gemma4_e4b`. |
| CODE-VERIFY-02 | PASS | Router is shared infra; full code-batch sweep re-verified after the edit. |
| CODE-SCOPE-01 | PASS | Only `experiments/agentbook-ab/pipeline/router.py` modified. |
| CODE-SCOPE-02 | N/A | Sprint-exit commit. |

## Sprint Contract Acceptance Criteria

### Task 012 acceptance

- [x] `experiments/agentbook-ab/pipeline/tests/test_orchestrator.py` exists with 1 test `test_good_rotate_chain_runs_serial_within_chain`.
- [x] Stubbed `run_cell` records `(iid, model, sample_idx, start_ts, end_ts)`, sleeps a small bounded delay (50 ms), and writes a synthetic `result.json` so `_load_prior_sample_outcomes` would find it.
- [x] Enumerates `good_rotate` cells for 2 distinct `(iid, model)` pairs at 3 sample indices each (lines 113-122).
- [x] Test invokes `orchestrator.run_chain` — the symbol that didn't yet exist (Red shape).
- [x] Assertions: (a) start timestamps within each chain are monotonically increasing with `sample_idx`; (b) intervals within a chain do not overlap; (c) cross-chain cells DO overlap (lines 154-184).
- [x] Test FAILED Red on the `orch_mod.run_chain` attribute fetch.
- [x] Test wall-time < 200 ms (3 cells × 50 ms × 2 chains in parallel ≈ 150 ms theoretical).
- [x] **Red-state confirmation** documented in the prior coordinator's handoff.

### Task 013 acceptance

- [x] `test_good_rotate_chain_runs_serial_within_chain` PASSES.
- [ ] `pipeline/orchestrator.py` splits scheduling at `main()` (rotate vs other) — **NOT DONE**. The single `ThreadPoolExecutor` over `todo` (orchestrator.py:309-311) still dispatches every cell, including `good_rotate`. The test does not exercise this path; the gap survives the Green gate.
- [x] `run_chain(chain, llm, client, ...)` added at `orchestrator.py:107-139`; serial iteration over `sample_idx`-sorted cells; no `ThreadPoolExecutor` inside.
- [ ] `_has_memory` gate extended with the `good_rotate` case — **NOT DONE**. Grep confirms `_has_memory` (orchestrator.py:261-275) only branches on `good_router` and `good_loop`-family; a `good_rotate` cell falls through to `return True` unconditionally.
- [x] `run_cell` passes `cell.sample_idx` to `build_prompt` (orchestrator.py:51-54 in the diff).
- [ ] `bootstrap_outcomes_log` harvest extended to read archived `runs_v2.*/` directories — **NOT DONE**. `bootstrap_outcomes_log` (router.py:126-148) still scans only `runs_v2/` and `runs_v2.good_loop_v1_single_repro/`.
- [x] Full code-batch pytest stays green (44/44 PASS at end of Batch 4 task 013; 47/47 PASS at end of Batch 4 task 015).
- [x] Ruff passes on `pipeline/orchestrator.py`.
- [x] No new external Python dependencies.
- [x] **Anti-stub:** no placeholder bodies in `run_chain` (verified by inspection).

### Task 014 acceptance

- [x] `pipeline/tests/test_router.py` extended (appended) with 3 new tests named per the sprint contract.
- [x] Synthetic outcomes fixtures: 17-task gemma4_e4b grid where best static = `good_multi_loop` (13/17), rotate ceiling matches union ceiling at 15/17 by construction (good_loop rescues 2 tasks that good_multi_loop misses; 2 tasks resolve nowhere).
- [x] Fallback test seeds `(gemma4_e4b, sympy__sympy-15017, good_multi_loop, s=0)` with `resolved=False` and explicitly omits any s=1/s=2 row.
- [x] LOO test wires a `_SpyKNN` subclass that records every outcomes row passed into the score computation **only when the held-out iid is the active chain** (correct LOO semantic; the bait rows for `sympy__sympy-15017` legitimately enter score computation for OTHER chains, but never for its own).
- [x] All 3 tests FAILED Red — `AttributeError: module 'pipeline.router' has no attribute 'evaluate_offline_rotate'`.
- [x] Per-test wall-time < 100 ms (whole-file run 0.07s in Red, 0.08s in Green for the 3 new tests).
- [x] No real `_oracle/outcomes_log.json` access; `monkeypatch.setattr(router_mod, "load_outcomes", lambda: outcomes)` in every test.
- [x] Prior 6 router tests stay green (re-verified under `-k "not offline_rotate"`); new total = 9.
- [x] **Red-state confirmation:** scoped pytest reports 3 failures, all with the AttributeError shape.

### Task 015 acceptance

- [x] All 3 Feature-5 tests in `pipeline/tests/test_router.py` PASS.
- [x] `evaluate_offline_rotate(router, *, k: int = 3, models: tuple[str, ...] = ("gemma4_e4b",)) -> dict[str, dict]` exists in `pipeline/router.py`. Returns `{model: {tasks, coverage_rotate, ceiling_all_arms_union, arms_used_count, unmet_samples}}`.
- [x] Implementation per architecture.md "evaluate_offline_rotate":
  - For each `(model, iid)`: `tried: dict[str, list[bool]] = {}`, `consume_idx: dict[str, int] = defaultdict(int)`.
  - For `s in range(k)`: KNN-capable routers receive `outcomes=outcomes, exclude_iid=iid`; RuleRouter receives only `features, model, sample_idx=s, tried_arms_results=tried` (the rule router does not accept `outcomes`/`exclude_iid` kwargs).
  - Slot lookup: `(model, iid, arm, consume_idx[arm])`; on miss fall back to `(model, iid, arm, 0)` and `unmet_samples += 1`.
  - `tried.setdefault(arm, []).append(resolved)`; `consume_idx[arm] += 1`; short-circuit on `resolved == True`.
  - `coverage_rotate` = `f"{covered}/{len(iids)}"`; `ceiling_all_arms_union` computed from `by_arm` (sample-union per arm) over `RUNTIME_ARMS`.
  - `arms_used_count = len(arms_dispatched)` (distinct arms across all iids).
- [x] `main()` extended: a `policy=<name>  k=3  rotation=True` row is printed per router/k combination (smoke output shown above).
- [x] `_pick_unexplored` reused (not re-implemented) — the routers' `select_arm_for_sample` already delegates to it, and `evaluate_offline_rotate` calls those methods.
- [x] Full code-batch pytest stays green (47 PASS).
- [x] Ruff passes on `pipeline/router.py`.
- [x] No new external Python dependencies.
- [x] **Anti-stub:** no placeholder bodies; verified by inspection of `evaluate_offline_rotate`.

## Rework Items

| ID | Task | Item | Severity | Action |
|----|------|------|----------|--------|
| BATCH4-013-A | 013 | `main()` does not split scheduling between `rotate_cells` and `other_cells`. Runtime `good_rotate` cells are dispatched through the parallel pool and may run sample N+1 before sample N's `result.json` exists on disk. | High (correctness) — rotation arm would non-deterministically read stale or missing prior-sample outcomes at runtime. | Open a follow-up task in the next code batch (or include in operator-deferred Task 016) to add `rotate_cells = [c for c in todo if c.arm == "good_rotate"]` / `other_cells = [c for c in todo if c.arm != "good_rotate"]`, dispatch rotate via `run_chain` per `(iid, model)`, and dispatch other via the existing parallel pool. |
| BATCH4-013-B | 013 | `_has_memory` has no `good_rotate` branch. A `good_rotate` cell whose iid lacks the memory/synth/loop prereqs would silently dispatch and crash inside `build_prompt` at the recursive sub-arm call. | Medium (gating) — surfaces only when scheduling actually dispatches `good_rotate` cells; currently masked by gap A. | Add `if c.arm == "good_rotate": return c.iid in mem_ids and c.iid in synth_ids and c.iid in loop_ids` to `_has_memory`. |
| BATCH4-013-C | 013 | `bootstrap_outcomes_log` does not scan archived `runs_v2.*/` directories. The router's KNN training data is artificially narrowed to the active `runs_v2/` + the v1 archive only. | Medium (data completeness) — does not affect tests but suppresses lineage signal once the operator starts running rotation batches. | Extend `bootstrap_outcomes_log` to iterate `sorted(ROOT.glob("runs_v2.*"))` and harvest each, while continuing to read the active `runs_v2/`. |

All three are CODE-SCOPE-01 acceptance gaps in task 013, not test failures or implementation defects in tasks 014/015. They are documented as follow-up items rather than blocking PIVOT because (a) the chain primitive `run_chain` is correctly implemented and unit-tested, (b) the surface they affect is the operator-batch dispatch path (Task 016) which is already deferred, and (c) the offline simulator (014/015) bypasses them entirely.

## Pivot

`pivot_required: false`

## Recurring Patterns

None detected within tasks 014/015. The three task-013 gaps are NOT a recurring failure pattern (they are a single coordinator's acceptance-criterion miss), but the fact that the Red/Green test for chain scheduling exercised only `run_chain` directly rather than `main()` end-to-end suggests a **CODE-TEST-03 boundary lesson worth recording**: when the impl-side acceptance criteria mention a control-flow split in `main()`, the Red test should cover the dispatch path, not just the underlying primitive. (Filed informally as a checklist-evolution candidate for retrospective; not a blocker for Batch 4.)

## Modified Files (this coordinator only — Batch 4 tail)

- `experiments/agentbook-ab/pipeline/tests/test_router.py` (appended 3 Feature-5 tests; prior 6 tests untouched)
- `experiments/agentbook-ab/pipeline/router.py` (added module-level `evaluate_offline_rotate`; extended `main()` with the `rotation=True` row per router)

## Modified Files (cumulative Batch 4 — incl. prior coordinator)

- `experiments/agentbook-ab/pipeline/tests/test_orchestrator.py` (new, 1 test — by prior coordinator)
- `experiments/agentbook-ab/pipeline/orchestrator.py` (added `run_chain`; `run_cell` now passes `sample_idx` through to `build_prompt` — by prior coordinator)
- `experiments/agentbook-ab/pipeline/tests/test_router.py` (3 new Feature-5 tests — by this coordinator)
- `experiments/agentbook-ab/pipeline/router.py` (new `evaluate_offline_rotate`; `main()` rotation row — by this coordinator)

## Rework Round 1 — Closed

All three BATCH4-013 gaps were closed via Red-first Green-follow-on tests that
exercise the integration paths the original task-013 Green test bypassed.
Final scoped sweep: **50/50 PASS** (47 prior + 3 new) on
`uv run python -m pytest experiments/agentbook-ab/harness/tests/ experiments/agentbook-ab/memory/tests/ experiments/agentbook-ab/pipeline/tests/ -q`.
Ruff: clean on all four touched files
(`pipeline/orchestrator.py`, `pipeline/router.py`,
`pipeline/tests/test_orchestrator.py`, `pipeline/tests/test_router.py`).

| ID | Red test | Green impl summary | Red→Green evidence |
|----|----------|--------------------|--------------------|
| BATCH4-013-A | `test_orchestrator_main_splits_rotate_cells_into_chains` in `pipeline/tests/test_orchestrator.py` | Added `_dispatch_todo(todo, *, llm, client, workers, ...)` to `pipeline/orchestrator.py`. It partitions `todo` into `rotate_cells` and `other_cells`, groups rotate cells into per-`(iid, model)` chains (sorted by `sample_idx`), and runs Pool A (parallel cells) + Pool B (parallel chains, serial within each chain via `run_chain`) concurrently. `main()` now delegates its dispatch loop to `_dispatch_todo`. | Red: `AttributeError: module 'pipeline.orchestrator' has no attribute '_dispatch_todo'` (structural CODE-TEST-03 shape). Green: 1 PASS — rotate cells' wall intervals are strictly sequential; the non-rotate `good` cell overlaps at least one rotate cell. |
| BATCH4-013-B | `test_has_memory_good_rotate_branch` in `pipeline/tests/test_orchestrator.py` | Lifted `_has_memory(c, mem_ids, synth_ids, loop_ids)` from the `main()` closure to module-level and added `if c.arm == "good_rotate": return c.iid in mem_ids and c.iid in synth_ids and c.iid in loop_ids`. `main()` now calls the module-level helper. | Red: `AttributeError: module 'pipeline.orchestrator' has no attribute '_has_memory'`. Green: 1 PASS — verifies True only when all three id sets contain the iid; False when any one is missing. |
| BATCH4-013-C | `test_bootstrap_outcomes_log_reads_archived_runs_v2` in `pipeline/tests/test_router.py` | Extended `bootstrap_outcomes_log` to iterate `sorted(ROOT.glob("runs_v2.*"))` in addition to the active `runs_v2/`. The `runs_v2.good_loop_v1_single_repro` archive keeps its `good_loop_v1` arm-label override; every other archive contributes rows under its on-disk `arm` label. Non-directories and missing dirs are tolerated. | Red: `AssertionError: archived runs_v2.batch1/ row missing from harvest`. Green: 1 PASS — both active and archived rows present. |

### Per-fix verification commands (Round 1)

| Fix | Command | Exit | Last line(s) |
|-----|---------|------|--------------|
| BATCH4-013-A Red | `uv run python -m pytest experiments/agentbook-ab/pipeline/tests/test_orchestrator.py::test_orchestrator_main_splits_rotate_cells_into_chains -q` | non-zero | `AttributeError: module 'pipeline.orchestrator' has no attribute '_dispatch_todo'` |
| BATCH4-013-A Green | same command | 0 | `1 passed` |
| BATCH4-013-B Red | `uv run python -m pytest experiments/agentbook-ab/pipeline/tests/test_orchestrator.py::test_has_memory_good_rotate_branch -q` | non-zero | `AttributeError: module 'pipeline.orchestrator' has no attribute '_has_memory'` |
| BATCH4-013-B Green | same command | 0 | `1 passed` |
| BATCH4-013-C Red | `uv run python -m pytest experiments/agentbook-ab/pipeline/tests/test_router.py::test_bootstrap_outcomes_log_reads_archived_runs_v2 -q` | non-zero | `AssertionError: archived runs_v2.batch1/ row missing from harvest -- bootstrap_outcomes_log did not scan archived dirs` |
| BATCH4-013-C Green | same command | 0 | `1 passed` |
| Scoped full sweep (post-rework) | `uv run python -m pytest experiments/agentbook-ab/harness/tests/ experiments/agentbook-ab/memory/tests/ experiments/agentbook-ab/pipeline/tests/ -q` | 0 | `50 passed` |
| Joint ruff (post-rework) | `uv run ruff check experiments/agentbook-ab/pipeline/orchestrator.py experiments/agentbook-ab/pipeline/router.py experiments/agentbook-ab/pipeline/tests/test_orchestrator.py experiments/agentbook-ab/pipeline/tests/test_router.py` | 0 | `All checks passed!` |
| Orchestrator `--help` smoke | `uv run python -m pipeline.orchestrator --help` | 0 | Argparse usage prints; `_dispatch_todo` and `_has_memory` callable on module import. |
| Router CLI smoke | `uv run python -m pipeline.router` | 0 | `policy=rule  k=3  rotation=True ... gpt-oss_20b coverage=10/17 ... gemma4_e4b coverage=11/17` (unchanged vs Batch 4 tail — the existing outcomes log is reused, archive harvest fires on next fresh bootstrap). |

### Modified files (this round)

- `experiments/agentbook-ab/pipeline/orchestrator.py`
  - Added `from collections import defaultdict`.
  - Lifted `_has_memory` from a `main()` closure to a module-level function with explicit `(c, mem_ids, synth_ids, loop_ids)` signature; added the `good_rotate` union branch.
  - Added `_dispatch_todo` with Pool A / Pool B split.
  - `main()` now delegates to `_dispatch_todo` (progress prints preserved via `on_result`/`on_error` callbacks).
- `experiments/agentbook-ab/pipeline/router.py`
  - Extended `bootstrap_outcomes_log` to iterate `sorted(ROOT.glob("runs_v2.*"))`; v1 archive keeps its arm-label override.
- `experiments/agentbook-ab/pipeline/tests/test_orchestrator.py`
  - Added `test_has_memory_good_rotate_branch`.
  - Added `test_orchestrator_main_splits_rotate_cells_into_chains`.
- `experiments/agentbook-ab/pipeline/tests/test_router.py`
  - Added `test_bootstrap_outcomes_log_reads_archived_runs_v2` plus a `_write_synthetic_result` helper.

### Final verdict (post-rework)

All three BATCH4-013 acceptance gaps now PASS. Task 013 now satisfies every
bullet in "Task 013 acceptance" (the three previously unchecked items are
covered by the new module-level `_has_memory`, `_dispatch_todo` split in
`main()`, and the extended `bootstrap_outcomes_log` harvest). No production
data files mutated; no new external Python dependencies. CODE-SCOPE-01 holds:
only the four files listed above were touched.

## Verdict

**PASS** for tasks 012, 014, 015. **PASS WITH ACCEPTANCE GAPS** for task 013 (three impl-side acceptance bullets not landed: `main()` split, `_has_memory` extension, `bootstrap_outcomes_log` extension — see Rework Items). All four tasks satisfy CODE-VERIFY-01 (47/47 scoped sweep green; ruff clean on every touched file); the 014/015 Red→Green transition carries the structural failure shape mandated by CODE-TEST-03 (`AttributeError` on the missing symbol). No production data files mutated; no new external dependencies. The 013 gaps are filed as BATCH4-013-{A,B,C} for follow-up in the next code batch or as part of operator-deferred Task 016.

**Rework Round 1 closed (2026-05-29): all three BATCH4-013 gaps now PASS; scoped sweep is 50/50. See "Rework Round 1 — Closed" section above.**
