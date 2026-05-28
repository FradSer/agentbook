# Handoff Summary — Batch 3

## Completed Tasks

| ID  | Subject | Checklist Result | Batch |
|-----|---------|------------------|-------|
| 008 | select_arm_for_sample router tests (Feature 4 scenarios 1-6) | PASS — 5/6 Red as AttributeError, scenario-6 (signature-backcompat) Green throughout; 6/6 Green after 009 | 3 |
| 009 | select_arm_for_sample implementation on RuleRouter and KNNRouter | PASS — `_pick_unexplored` module-level, both routers extended, `select_arms` signature byte-identical; 42/42 scoped pytest | 3 |
| 010 | good_rotate arm + arm_meta routing record test (Feature 4 scenario 7) | PASS — Red shape was clean TypeError on missing `sample_idx` kwarg | 3 |
| 011 | good_rotate branch in arm_context.py + _load_prior_sample_outcomes | PASS — branch + reader + `sample_idx` kwarg landed; 43/43 scoped pytest | 3 |

## Remaining Tasks

| ID  | Subject | Status | Dependencies |
|-----|---------|--------|--------------|
| 012 | Serial-within-chain scheduling test | pending | 011 |
| 013 | Orchestrator chain scheduling implementation | pending | 012 |
| 014 | evaluate_offline_rotate simulator tests (Feature 5) | pending | 009 |
| 015 | evaluate_offline_rotate implementation + main() CLI integration | pending | 014 |
| 016 | Batch 3 exit gate (offline + online good_rotate sweep) | operator-deferred | 013, 015 |

## Key Decisions (Batch 3)

- **`_pick_unexplored` is module-level** in `pipeline/router.py` (not a method). Task-015's `evaluate_offline_rotate` reuses the same helper unchanged.
- **`select_arms` signature byte-for-byte unchanged.** PLAN-DEP / Feature 4 Scenario 6 backwards-compat preserved; existing `good_router` arm continues to call `select_arms` unaffected.
- **`KNNRouter.select_arm_for_sample` accepts `outcomes` and `exclude_iid` kwargs** for LOO safety; `RuleRouter` does not (no LOO concept).
- **`RUNS_V2` re-exported on `pipeline.arm_context`** so the new test can monkeypatch the runs root without coupling fixtures to `harness.sandbox`. Minor, in-scope infrastructure helper.
- **`build_prompt` signature is now `(iid, arm, *, client, model_slug, sample_idx=None)`.** Existing positional callers (which pass `iid, arm` positionally then everything else as kwargs) are unaffected; the orchestrator change to actually thread `sample_idx` through `Cell` waits until Batch 4 task-013.
- **`good_rotate` branch reads `cache = json.loads(SYNTH_CACHE.read_text())`** each call rather than going through the cached `_synth_data` global. This matches the architecture spec and keeps per-test fixture loads cheap.

## File Ownership (cumulative)

| File Path | Last Modified By Task |
|---|---|
| `experiments/agentbook-ab/harness/prompts.py` | 003 |
| `experiments/agentbook-ab/harness/agent_loop.py` | 003 |
| `experiments/agentbook-ab/harness/tests/test_search_replace.py` | 002 |
| `experiments/agentbook-ab/harness/llm_ollama.py` | 001 (net diff 0) |
| `experiments/agentbook-ab/memory/refine_from_outcomes.py` | 006 |
| `experiments/agentbook-ab/memory/tests/__init__.py` | 005 |
| `experiments/agentbook-ab/memory/tests/test_refine_from_outcomes.py` | 005 |
| `experiments/agentbook-ab/pipeline/router.py` | 009 |
| `experiments/agentbook-ab/pipeline/arm_context.py` | 011 (`good_rotate` branch + `_load_prior_sample_outcomes` + `sample_idx` kwarg + `RUNS_V2` re-export; Batch 2 task 006 added the `_synth_entry` revision-aware reader) |
| `experiments/agentbook-ab/pipeline/tests/__init__.py` | 008 |
| `experiments/agentbook-ab/pipeline/tests/test_router.py` | 008 |
| `experiments/agentbook-ab/pipeline/tests/test_arm_context.py` | 010 |
| `experiments/agentbook-ab/runs_v2.preflight/` | 001 (local-only per .gitignore) |
| `docs/plans/2026-05-27-agentbook-outcome-loop-plan/sprint-contract-batch-{1,2,3}.md` | (main agent) |
| `docs/plans/2026-05-27-agentbook-outcome-loop-plan/handoff-state.md` | (main agent; refreshed each batch) |
| `docs/plans/2026-05-27-agentbook-outcome-loop-plan/handoff-summary-{1,2,3}.md` | (main agent) |
| `docs/plans/2026-05-27-agentbook-outcome-loop-plan/evaluation-round-1-batch-{2,3}.md` | (coordinator inline audit) |

## Blockers

None for code work. Wall-time blocks operator-deferred ops tasks (004/007/016).
