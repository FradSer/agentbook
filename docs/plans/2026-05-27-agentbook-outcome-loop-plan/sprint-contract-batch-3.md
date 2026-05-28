# Batch 3 Sprint Contract

## Tasks

| ID  | Subject | Type |
|-----|---------|------|
| 008 | select_arm_for_sample router tests (Feature 4 scenarios 1-6) | test |
| 009 | select_arm_for_sample implementation on RuleRouter and KNNRouter | impl |
| 010 | good_rotate arm + arm_meta routing record test (Feature 4 scenario 7) | test |
| 011 | good_rotate branch in arm_context.py + _load_prior_sample_outcomes | impl |

Two sequential Red-Green pairs. **Batch 4** will pick up tasks 012-015 (chain scheduling + offline simulator); **task 016** (Batch 3 exit gate ops sweep) is operator-deferred outside the code-execution pipeline.

## Acceptance Criteria

### Task 008: select_arm_for_sample router tests (Feature 4 scenarios 1-6)

- [ ] `experiments/agentbook-ab/pipeline/tests/__init__.py` exists (empty file).
- [ ] `experiments/agentbook-ab/pipeline/tests/test_router.py` exists with 6 test functions, one per Feature 4 scenario (scenarios 1-6).
- [ ] Tests 1-5 FAIL Red — `AttributeError: '...Router' object has no attribute 'select_arm_for_sample'` is the expected failure shape (clean structural failure naming the missing method per CODE-TEST-03). Test 6 (signature-backcompat) may pass coincidentally and stays green.
- [ ] Per-test wall-time < 50 ms (in-memory fixtures only).
- [ ] Each test docstring references the scenario name from `bdd-specs.md` Feature 4.
- [ ] No new external Python dependencies.
- [ ] No other test file regresses (`uv run python -m pytest experiments/agentbook-ab/harness/tests/ experiments/agentbook-ab/memory/tests/ -q` stays 36/36).
- [ ] **Red-state confirmation:** `uv run python -m pytest experiments/agentbook-ab/pipeline/tests/test_router.py -q` reports 5 failures matching the AttributeError shape.

### Task 009: select_arm_for_sample implementation on RuleRouter and KNNRouter

- [ ] All 6 tests in `pipeline/tests/test_router.py` PASS.
- [ ] `_pick_unexplored(ranking: list[str], tried_arms_results: dict[str, list[bool]]) -> str` is **module-level** in `pipeline/router.py` (so `evaluate_offline_rotate` can reuse it in task-015). Decision order: REPLAY_WIN → FRESH_ARM → EXHAUSTED_RANKING → BURN_REPLAY.
- [ ] `RuleRouter.select_arm_for_sample(self, features, model_slug, sample_idx, tried_arms_results) -> str` exists; body calls `self.select(features, model_slug, k=len(RUNTIME_ARMS))` then delegates to `_pick_unexplored`.
- [ ] `KNNRouter.select_arm_for_sample(self, features, model_slug, sample_idx, tried_arms_results, *, outcomes=None, exclude_iid=None) -> str` exists; LOO-safe via `exclude_iid` passthrough to `self.select`.
- [ ] `select_arms` signature byte-for-byte unchanged (PLAN-DEP / Scenario 6 backwards-compat).
- [ ] Full code-batch pytest stays green (`harness/tests/` + `memory/tests/` + `pipeline/tests/`).
- [ ] Ruff passes on `pipeline/router.py`.
- [ ] No new external Python dependencies.
- [ ] **Anti-stub:** no `TODO`/`FIXME`/`NotImplementedError`/`pass`-only bodies.

### Task 010: good_rotate arm + arm_meta routing record test (Feature 4 scenario 7)

- [ ] `experiments/agentbook-ab/pipeline/tests/test_arm_context.py` exists with 1 test function `test_good_rotate_cell_records_arm_meta` (or a clearly named equivalent).
- [ ] Test fixture under `tmp_path` materialises `runs_v2/sympy__sympy-15017__good_rotate__gemma4_e4b__s0/result.json` with `{"resolved": false, "arm_meta": {"routed_to": "good_multi_loop"}}` and a minimal `_oracle/synth_cache.json` with an entry for `"sympy__sympy-15017"`. Module-level paths monkey-patched (`SYNTH_CACHE`, runs root).
- [ ] Test calls `build_prompt("sympy__sympy-15017", "good_rotate", client=stub_client, model_slug="gemma4_e4b", sample_idx=1)` and asserts: `meta["routed_from"] == "good_rotate"`, `meta["routed_to"] in RUNTIME_ARMS` and `!= "good_rotate"`, `meta["rotate_sample_idx"] == 1`, `meta["rotate_tried_history"] == {"good_multi_loop": [False]}`.
- [ ] Test FAILS Red — `good_rotate` branch does not exist or `_load_prior_sample_outcomes` is missing → `build_prompt` raises or returns a no-op stub.
- [ ] Test wall-time < 50 ms; no real Ollama; no real synth_cache mutation.
- [ ] No other test file regresses.
- [ ] **Red-state confirmation:** same pytest invocation reports exactly 1 failure in the new test, with no impact on 36/36 prior tests.

### Task 011: good_rotate branch implementation

- [ ] `experiments/agentbook-ab/pipeline/arm_context.py` carries the `good_rotate` branch (peer to `good_router` at lines 211-226), plus module-level `_load_prior_sample_outcomes(iid: str, model_slug: str, sample_idx: int) -> dict[str, list[bool]]`, plus `sample_idx: int | None = None` added to `build_prompt`'s signature (trailing kwarg).
- [ ] `_load_prior_sample_outcomes` returns `{}` when `sample_idx == 0`; aggregates `arm_meta.routed_to → [resolved_bool, ...]` across prior samples otherwise; tolerant to missing directories.
- [ ] `good_rotate` branch guards: `missing_model` when `model_slug` is unset; `no_features` when `iid` not in cache.
- [ ] `good_rotate` branch consults `_ACTIVE_ROUTER.select_arm_for_sample`, recursively calls `build_prompt` with the chosen sub-arm, stamps `meta["routed_from"]="good_rotate"`, `meta["routed_to"]=sub_arm`, `meta["rotate_sample_idx"]=sample_idx`, `meta["rotate_tried_history"]=tried`, `meta["hint"]="good_rotate"`.
- [ ] `test_good_rotate_cell_records_arm_meta` PASSES.
- [ ] Full code-batch pytest stays green (`harness/tests/` + `memory/tests/` + `pipeline/tests/` = 36 + 6 + 1 = 43 PASS).
- [ ] Ruff passes on `pipeline/arm_context.py`.
- [ ] Existing positional callers of `build_prompt` unaffected (trailing kwarg).
- [ ] No new external Python dependencies.
- [ ] **Anti-stub:** no placeholder bodies.

## Red-Green Pairs

| Test Task | Impl Task | Expected Red State | Expected Green State |
|-----------|-----------|--------------------|----------------------|
| 008 | 009 | 5/6 fails (AttributeError on `select_arm_for_sample`); test 6 passes coincidentally | 6/6 PASS |
| 010 | 011 | 1/1 fails (no `good_rotate` branch in build_prompt) | 1/1 PASS; cumulative 43/43 |

Sequential within the coordinator: complete 008→009 fully (verification + ruff) before starting 010, since 010's fixture stubs the `select_arm_for_sample` method that 009 introduces.

## Evaluation Criteria Preview

| Item ID | Description |
|---------|-------------|
| CODE-ASSUME-01 | Grep for existing symbols (`RUNTIME_ARMS`, `_ACTIVE_ROUTER`, `select_arms`, `extract_features`) before naming them in tests |
| CODE-ASSUME-02 | Confirm `Cell` dataclass field set in `pipeline/orchestrator.py` before assuming `sample_idx` shape — relevant for task-011 even though orchestrator changes wait until Batch 4 |
| CODE-EDIT-01 | Re-Read modified files between Edits when a formatter may run |
| CODE-LINT-01 | Ruff after each task |
| CODE-TEST-01 | In-memory fixtures only; no real Ollama; no real `_oracle/*.json` mutation |
| CODE-TEST-03 | Red shape is clean AttributeError/missing-branch, not incidental fixture errors |
| CODE-VERIFY-01 | Both per-task pytest AND scoped regression sweep exit 0 before marking complete |
| CODE-VERIFY-02 | Touching `pipeline/router.py` and `pipeline/arm_context.py` (shared infra) re-runs the full code-batch suite |
| CODE-SCOPE-01 | Stay within declared file lists |
| CODE-SCOPE-02 | Commit message names the feature scope, not file moves |

## Sign-off

- **Generator:** executing-plans
- **Timestamp:** 2026-05-29T01:20:00Z
- **Status:** READY
- **Revision:** 0
