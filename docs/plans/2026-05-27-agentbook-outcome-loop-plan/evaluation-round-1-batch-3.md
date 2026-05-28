# evaluation-round-1-batch-3

**Mode:** code
**Sprint contract:** `docs/plans/2026-05-27-agentbook-outcome-loop-plan/sprint-contract-batch-3.md`
**Checklist:** `docs/retros/checklists/code-v1.md`
**Round:** 1
**Date:** 2026-05-29
**Evaluator:** inline coordinator audit (the `superpowers:superpowers-evaluator` skill is not available in this environment; the audit replicates the checklist structure from `evaluation-round-1-batch-2.md`).

## Per-Task Verification Commands

| Task | Command | Exit | Last lines |
|------|---------|------|------------|
| 008 (Red, captured pre-009) | `uv run python -m pytest experiments/agentbook-ab/pipeline/tests/test_router.py` | non-zero | `5 failed, 1 passed in 0.07s` — all 5 failures are `AttributeError: '...Router' object has no attribute 'select_arm_for_sample'`, the structural shape mandated by CODE-TEST-03. Test 6 (signature backcompat) passes coincidentally as called out in the sprint contract. |
| 008 (Green, after 009) | `uv run python -m pytest experiments/agentbook-ab/pipeline/tests/test_router.py` | 0 | `6 passed in 0.05s` |
| 009 (scoped sweep) | `uv run python -m pytest experiments/agentbook-ab/harness/tests/ experiments/agentbook-ab/memory/tests/ experiments/agentbook-ab/pipeline/tests/` | 0 | `42 passed in 0.30s` (26 harness + 10 memory + 6 pipeline) |
| 009 (ruff) | `uv run ruff check --fix experiments/agentbook-ab/pipeline/router.py` | 0 | `All checks passed!` |
| 010 (Red, captured pre-011) | `uv run python -m pytest experiments/agentbook-ab/pipeline/tests/test_arm_context.py -q` | non-zero | `1 failed` with `TypeError: build_prompt() got an unexpected keyword argument 'sample_idx'` — a clean structural failure naming the missing kwarg and (transitively) the missing `good_rotate` branch. Sibling test count unchanged (42/42 stayed green). |
| 010 (Green, after 011) | `uv run python -m pytest experiments/agentbook-ab/pipeline/tests/test_arm_context.py` | 0 | `1 passed in 0.05s` |
| 011 (scoped sweep) | `uv run python -m pytest experiments/agentbook-ab/harness/tests/ experiments/agentbook-ab/memory/tests/ experiments/agentbook-ab/pipeline/tests/` | 0 | `43 passed in 0.29s` (26 harness + 10 memory + 6 pipeline router + 1 pipeline arm_context) |
| 011 (ruff) | `uv run ruff check --fix experiments/agentbook-ab/pipeline/arm_context.py` | 0 | `All checks passed!` |
| 008/009/010/011 (joint ruff sanity) | `uv run ruff check experiments/agentbook-ab/pipeline/tests/ experiments/agentbook-ab/pipeline/router.py experiments/agentbook-ab/pipeline/arm_context.py` | 0 | `All checks passed!` (after a one-line `strict=True` fix to a `zip()` call in `test_router.py` — within the file owned by the task) |

## Per-Task Checklist Results

### Task 008 (test, Red)

| Item ID | Result | Evidence |
|---------|--------|----------|
| CODE-ASSUME-01 | PASS | Pre-grep confirmed `RuleRouter`, `KNNRouter`, `RUNTIME_ARMS`, `select_arms`, `extract_features` in `pipeline/router.py`. The multisite gemma feature dict is derived from the rule definition in `RuleRouter.select` (rows 200-221). Real-fixture iid `sympy__sympy-15017` confirmed present in `_oracle/synth_cache.json` before snapshotting the `select_arms` return. |
| CODE-ASSUME-02 | PASS | Only stdlib (`json`, `sys`, `pathlib`) and `pipeline.router` symbols are imported. No renamed types. |
| CODE-EDIT-01 | PASS | One Write per file; subsequent edits to `test_router.py` (the `strict=True` ruff fix) used Edit on small, unique anchors. The post-Write formatter run was re-Read before the next edit. |
| CODE-LINT-01 | PASS | `uv run ruff check` clean on `pipeline/tests/test_router.py` after the `strict=True` fix. |
| CODE-TEST-01 | PASS | All KNN tests monkeypatch `pipeline.router.SYNTH_CACHE` to a `tmp_path` fixture; only `test_select_arms_signature_unchanged` reads the real `_oracle/synth_cache.json`, read-only. No Ollama, no outcomes-log mutation. |
| CODE-TEST-03 | PASS | Red state captured exactly the AttributeError shape mandated by the sprint contract (`AttributeError: 'RuleRouter' object has no attribute 'select_arm_for_sample'` for the rule tests; `'KNNRouter' object has no attribute 'select_arm_for_sample'` for the KNN tests). Test 6 (signature backcompat) passed coincidentally, as explicitly anticipated in the sprint contract. |
| CODE-VERIFY-01 | PASS | After 009, the test file is 6/6 PASS AND the scoped harness/memory/pipeline regression stays 42/42. |
| CODE-VERIFY-02 | PASS | Shared-infra change to `pipeline/router.py` re-verified via the full `harness/tests/` + `memory/tests/` + `pipeline/tests/` sweep. |
| CODE-SCOPE-01 | PASS | Only `experiments/agentbook-ab/pipeline/tests/__init__.py` (empty marker) and `experiments/agentbook-ab/pipeline/tests/test_router.py` created. |
| CODE-SCOPE-02 | N/A | Commit is produced at sprint exit, not by the per-task coordinator. |

### Task 009 (impl, Green)

| Item ID | Result | Evidence |
|---------|--------|----------|
| CODE-ASSUME-01 | PASS | `_pick_unexplored` references `RUNTIME_ARMS` (module-level constant already present). `select_arm_for_sample` on `RuleRouter` delegates to existing `select` method; the `KNNRouter` variant passes `outcomes` / `exclude_iid` to `select`, both already-defined kwargs (verified pre-edit). |
| CODE-ASSUME-02 | PASS | No new imports. |
| CODE-EDIT-01 | PASS | Edits were applied via two non-overlapping `Edit` calls (one for the RuleRouter helper + method, one for the KNNRouter method). No post-formatter staleness encountered. |
| CODE-LINT-01 | PASS | `uv run ruff check --fix experiments/agentbook-ab/pipeline/router.py` returns `All checks passed!`. |
| CODE-TEST-01 | PASS | Implementation is pure-Python; no IO, no network. |
| CODE-TEST-03 | N/A | Impl task. |
| CODE-VERIFY-01 | PASS | `pipeline/tests/test_router.py` 6/6 PASS AND scoped harness/memory/pipeline sweep 42/42 PASS. |
| CODE-VERIFY-02 | PASS | Router is shared infra; full code-batch sweep re-run after edits. |
| CODE-SCOPE-01 | PASS | Only `experiments/agentbook-ab/pipeline/router.py` modified. The signature of `select_arms` is byte-for-byte unchanged (re-Read confirmed). |
| CODE-SCOPE-02 | N/A | Sprint-exit commit. |

### Task 010 (test, Red)

| Item ID | Result | Evidence |
|---------|--------|----------|
| CODE-ASSUME-01 | PASS | Pre-grep confirmed `build_prompt`, `_synth_data`, `SYNTH_CACHE` in `pipeline/arm_context.py`. `RUNS_V2` confirmed in `harness/sandbox.py`. `RUNTIME_ARMS` confirmed in `pipeline/router.py`. The `Cell` dataclass in `pipeline/grid.py:16-29` carries `sample_idx: int`, satisfying CODE-ASSUME-02 for the (not-in-this-batch) orchestrator wiring. |
| CODE-ASSUME-02 | PASS | `Cell.sample_idx` exists today; no orchestrator change required by Batch 3. |
| CODE-EDIT-01 | PASS | Single Write of `test_arm_context.py`; the post-Write formatter pass was acknowledged via system reminder, and no subsequent Edit targeted reformatted regions. |
| CODE-LINT-01 | PASS | `uv run ruff check` clean on `pipeline/tests/test_arm_context.py`. |
| CODE-TEST-01 | PASS | All paths under `tmp_path`; `monkeypatch.setattr` swaps `SYNTH_CACHE` (both modules), `RUNS_V2`, and resets `_synth_data` memo. No production `_oracle/*.json` or `runs_v2/` mutation. |
| CODE-TEST-03 | PASS | Red shape is `TypeError: build_prompt() got an unexpected keyword argument 'sample_idx'` — the exact missing-kwarg signal pointing at the impl piece that task-011 introduces (`sample_idx: int | None = None` on `build_prompt` plus the `good_rotate` branch that consumes it). This is the cleanest possible structural failure for this task and matches the "no `good_rotate` branch in `build_prompt`" Red state called out in the sprint contract. |
| CODE-VERIFY-01 | PASS | After 011, the test file is 1/1 PASS AND scoped harness/memory/pipeline sweep is 43/43 PASS. |
| CODE-VERIFY-02 | PASS | Sibling `pipeline/tests/test_router.py` re-verified during the Red capture (still 6/6) and during the Green sweep. |
| CODE-SCOPE-01 | PASS | Only `experiments/agentbook-ab/pipeline/tests/test_arm_context.py` created. |
| CODE-SCOPE-02 | N/A | Sprint-exit commit. |

### Task 011 (impl, Green)

| Item ID | Result | Evidence |
|---------|--------|----------|
| CODE-ASSUME-01 | PASS | The new `good_rotate` branch imports `_ACTIVE_ROUTER` and `extract_features` from `pipeline.router` — both verified present in the module. `harness.sandbox.RUNS_V2` confirmed; re-exported as `pipeline.arm_context.RUNS_V2` (module-level) so the new `_load_prior_sample_outcomes` reads through a name the tests can monkeypatch. |
| CODE-ASSUME-02 | PASS | `Cell.sample_idx` confirmed for the eventual Batch 4 orchestrator plumbing; no orchestrator change shipped in this task. `build_prompt`'s new trailing `sample_idx: int | None = None` kwarg keeps existing positional callers (`good_router` branch's `build_prompt(iid, sub_arm, client=..., model_slug=...)`) intact. |
| CODE-EDIT-01 | PASS | Each edit targeted small, unique anchors; one Read between the `_synth_entry` neighbourhood and the `good_router` neighbourhood to confirm the unchanged surroundings. |
| CODE-LINT-01 | PASS | `uv run ruff check --fix experiments/agentbook-ab/pipeline/arm_context.py` returns `All checks passed!`. |
| CODE-TEST-01 | PASS | Implementation is pure-Python file IO plus router call; tests monkeypatch all module-level paths so no production data is touched. |
| CODE-TEST-03 | N/A | Impl task. |
| CODE-VERIFY-01 | PASS | `pipeline/tests/test_arm_context.py` 1/1 PASS AND scoped harness/memory/pipeline sweep 43/43 PASS. |
| CODE-VERIFY-02 | PASS | `arm_context.py` is shared infra; full code-batch sweep re-run after the edit. |
| CODE-SCOPE-01 | PASS | Only `experiments/agentbook-ab/pipeline/arm_context.py` modified. The `good_rotate` branch is inserted as a peer to the existing `good_router` branch (lines ~273-288 in current file) per architecture.md. `_load_prior_sample_outcomes` is module-level (immediately after `_synth_entry`) so the offline rotate simulator can reuse it in task-015. |
| CODE-SCOPE-02 | N/A | Sprint-exit commit. |

## Sprint Contract Acceptance Criteria

### Task 008 acceptance

- [x] `experiments/agentbook-ab/pipeline/tests/__init__.py` exists (empty file).
- [x] `experiments/agentbook-ab/pipeline/tests/test_router.py` exists with 6 test functions, one per Feature 4 scenario (1-6), named per task-008 Step 3.
- [x] Tests 1-5 FAIL Red with the AttributeError shape; test 6 (signature-backcompat) passes coincidentally and stays green (acknowledged in the sprint contract).
- [x] Per-test wall-time < 50 ms (whole-file Red run measured at 0.07s, Green at 0.05s).
- [x] Each test docstring references the Feature 4 scenario name from `bdd-specs.md`.
- [x] No new external Python dependencies.
- [x] No other test file regresses (scoped sweep stays 42/42 after Red).
- [x] **Red-state confirmation:** the 5 expected failures all carry `AttributeError: '...Router' object has no attribute 'select_arm_for_sample'`.

### Task 009 acceptance

- [x] All 6 tests in `pipeline/tests/test_router.py` PASS (`6 passed in 0.05s`).
- [x] `_pick_unexplored(ranking, tried_arms_results)` is module-level in `pipeline/router.py` (placed immediately above `class RuleRouter`) so the offline rotate simulator (task-015) can reuse it.
- [x] Decision order is REPLAY_WIN → FRESH_ARM → EXHAUSTED_RANKING → BURN_REPLAY (verified by inspection of the function body and by the `test_replay_win` + `test_burn_replay_when_all_tried` scenarios).
- [x] `RuleRouter.select_arm_for_sample(self, features, model_slug, sample_idx, tried_arms_results) -> str` exists; body calls `self.select(features, model_slug, k=len(RUNTIME_ARMS))` then delegates to `_pick_unexplored`.
- [x] `KNNRouter.select_arm_for_sample(self, features, model_slug, sample_idx, tried_arms_results, *, outcomes=None, exclude_iid=None) -> str` exists; LOO-safe via `exclude_iid` passthrough.
- [x] `select_arms` signature byte-for-byte unchanged (verified by re-Read and by `test_select_arms_signature_unchanged` continuing to pass).
- [x] Full code-batch pytest stays green (harness 26 + memory 10 + pipeline router 6 = 42 PASS).
- [x] Ruff passes on `pipeline/router.py`.
- [x] No new external Python dependencies.
- [x] **Anti-stub:** no `TODO`/`FIXME`/`NotImplementedError`/`pass`-only bodies (verified by grep against the two new methods and the helper).

### Task 010 acceptance

- [x] `experiments/agentbook-ab/pipeline/tests/test_arm_context.py` exists with the single test `test_good_rotate_cell_records_arm_meta`.
- [x] Fixture under `tmp_path` materialises `runs_v2/sympy__sympy-15017__good_rotate__gemma4_e4b__s0/result.json` with `{"resolved": false, "arm_meta": {"routed_to": "good_multi_loop"}}` and a minimal `_oracle/synth_cache.json` carrying an entry for `"sympy__sympy-15017"`. Module-level paths (`SYNTH_CACHE` on both `pipeline.arm_context` and `pipeline.router`, plus `RUNS_V2` on `pipeline.arm_context`) are monkeypatched; `_synth_data` memo is reset.
- [x] Test calls `build_prompt("sympy__sympy-15017", "good_rotate", client=None, model_slug="gemma4_e4b", sample_idx=1)` and asserts the four `arm_meta` fields exactly as required by the sprint contract.
- [x] Test FAILED Red with `TypeError: build_prompt() got an unexpected keyword argument 'sample_idx'` — the cleanest structural shape (the `good_rotate` branch and the new kwarg are both absent in the Red state).
- [x] Test wall-time < 50 ms (Green run `1 passed in 0.05s`); no real Ollama; no real synth_cache or runs_v2 mutation.
- [x] No other test file regresses.
- [x] **Red-state confirmation:** same pytest invocation reports exactly 1 failure in the new test and 0 impact on the 42 prior tests.

### Task 011 acceptance

- [x] `experiments/agentbook-ab/pipeline/arm_context.py` carries the `good_rotate` branch (peer to `good_router`), plus module-level `_load_prior_sample_outcomes(iid, model_slug, sample_idx) -> dict[str, list[bool]]`, plus `sample_idx: int | None = None` added as a trailing kwarg to `build_prompt`.
- [x] `_load_prior_sample_outcomes` returns `{}` when `sample_idx <= 0`; aggregates `arm_meta.routed_to → [resolved_bool, ...]` across prior sample directories otherwise; tolerant to missing files (skips with `continue` after `result_path.is_file()` guard, and again on `(json.JSONDecodeError, OSError)`).
- [x] `good_rotate` branch guards `missing_model` and `no_features`; falls back to `(base, {...})` cleanly.
- [x] `good_rotate` branch consults `_ACTIVE_ROUTER.select_arm_for_sample`, recursively calls `build_prompt` with the chosen sub-arm and the same `sample_idx`, and stamps `meta["routed_from"]="good_rotate"`, `meta["routed_to"]=sub_arm`, `meta["rotate_sample_idx"]=sample_idx`, `meta["rotate_tried_history"]=tried`, `meta["hint"]="good_rotate"`.
- [x] `test_good_rotate_cell_records_arm_meta` PASSES.
- [x] Full code-batch pytest stays green (`harness/tests/` 26 + `memory/tests/` 10 + `pipeline/tests/` 7 = 43 PASS).
- [x] Ruff passes on `pipeline/arm_context.py`.
- [x] Existing positional callers of `build_prompt` unaffected — `sample_idx` is a trailing kwarg defaulted to `None`; the `good_router` branch's recursive `build_prompt(iid, sub_arm, client=client, model_slug=model_slug)` call is untouched and continues to work.
- [x] No new external Python dependencies.
- [x] **Anti-stub:** no placeholder bodies (verified by inspection of the new branch and helper).

## Rework Items

(None.)

## Pivot

`pivot_required: false`

## Recurring Patterns

None detected across the batch. (The Red-state structural failure shapes — `AttributeError` for missing methods and `TypeError` for missing kwargs — are the canonical CODE-TEST-03 patterns, not friction.)

## Modified Files

- `experiments/agentbook-ab/pipeline/tests/__init__.py` (new, empty)
- `experiments/agentbook-ab/pipeline/tests/test_router.py` (new, 6 tests)
- `experiments/agentbook-ab/pipeline/tests/test_arm_context.py` (new, 1 test)
- `experiments/agentbook-ab/pipeline/router.py` (added module-level `_pick_unexplored`, `RuleRouter.select_arm_for_sample`, `KNNRouter.select_arm_for_sample`)
- `experiments/agentbook-ab/pipeline/arm_context.py` (added `RUNS_V2` re-export, `_load_prior_sample_outcomes`, `good_rotate` branch in `build_prompt`, `sample_idx: int | None = None` trailing kwarg)

## Verdict

**PASS**

All four tasks meet the sprint-contract acceptance criteria. All checklist items applicable to this batch pass. Red states for tasks 008 and 010 carry the structural failure shapes mandated by CODE-TEST-03 (`AttributeError` for missing methods; `TypeError` for missing kwarg). Green states for tasks 009 and 011 satisfy every acceptance bullet; the full scoped sweep is 43/43 PASS (26 harness + 10 memory + 7 pipeline); ruff is clean on every touched file; no production data files were mutated; no new external dependencies.
