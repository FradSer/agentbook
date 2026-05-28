# Handoff State (cumulative cross-batch memory)

**Last updated:** 2026-05-29 (after Batch 3, before Batch 4)

## Completed Task IDs

- 001–003 (Batch 1 code: preflight + lenient parser)
- 004 (Batch 1 exit gate; OPERATOR-DEFERRED)
- 005, 006 (Batch 2 code: refinement script + `_synth_entry` revision-aware reader)
- 007 (Batch 2 exit gate; OPERATOR-DEFERRED)
- 008, 009 (Batch 3 code: `select_arm_for_sample` on RuleRouter + KNNRouter)
- 010, 011 (Batch 3 code: `good_rotate` arm + `_load_prior_sample_outcomes`)

## Modified Files (accumulated)

- `experiments/agentbook-ab/harness/{prompts.py, agent_loop.py, llm_ollama.py, tests/test_search_replace.py}` (Batch 1)
- `experiments/agentbook-ab/memory/{refine_from_outcomes.py, tests/__init__.py, tests/test_refine_from_outcomes.py}` (Batch 2)
- `experiments/agentbook-ab/pipeline/{router.py, arm_context.py, tests/__init__.py, tests/test_router.py, tests/test_arm_context.py}` (Batches 2-3)
- `experiments/agentbook-ab/runs_v2.preflight/` (Batch 1; local-only per .gitignore)

## Recurring Failure Patterns

None detected through Batches 1-3.

## Key Architectural Decisions Carried Forward (relevant to Batch 4)

- **`_pick_unexplored(ranking, tried_arms_results)` is module-level** in `pipeline/router.py`. Task-015's `evaluate_offline_rotate` reuses it without re-implementing.
- **`build_prompt(iid, arm, *, client, model_slug, sample_idx=None)`** signature is in place. Task-013 must update `pipeline/orchestrator.py`'s `run_cell` to pass `cell.sample_idx` through. Verify the `Cell` dataclass already carries `sample_idx`; if not, add it as a dataclass field.
- **`good_rotate` arm** is live in `pipeline/arm_context.py` and reads prior sample outcomes via `_load_prior_sample_outcomes(iid, model_slug, sample_idx)` which walks `runs_v2/<iid>__good_rotate__<model_slug>__s<j>/result.json`. This requires task-013's per-`(iid, model)` chain scheduling so sample N+1 reads sample N's `result.json` from disk.
- **`pipeline.router._ACTIVE_ROUTER`** module-level global is the swap point. `evaluate_offline_rotate` runs against whichever router is passed; the orchestrator uses `_ACTIVE_ROUTER`.
- **LOO safety for KNN:** task-009 added `outcomes` and `exclude_iid` kwargs to `KNNRouter.select_arm_for_sample`. Task-015's offline simulator must thread these per `(model, iid)` so the held-out iid never enters the KNN score computation. RuleRouter does not need LOO.
- **Existing `select_arms` callers unaffected.** `good_router` arm still uses `select_arms`; only the new `good_rotate` arm uses `select_arm_for_sample`. Don't refactor `select_arms` callers in this batch.
- **`bootstrap_outcomes_log` harvest extension** is part of task-013 (extend to read archived `runs_v2.*/` directories). Confirm against the existing `bootstrap_outcomes_log` shape in `pipeline/router.py` before modifying.
- **`evaluate_offline` (existing)** is the structural model for `evaluate_offline_rotate` (existing in `pipeline/router.py` already; mirror its style for LOO loop, arm-level pass@k computation, CLI integration).

## Cross-Batch Invariants

- Each batch is its own commit (Batch 1=`d4e94f4`, Batch 2=`8f56528`, Batch 3=`913eb22` + `6ec2fbb`).
- `_oracle/outcomes_log.json` is the single source of truth for `K_pre`/`K_post`.
- `runs_v2.{preflight,batch1,batch2,batch3}/` archive convention.
- `uv run python -m pytest experiments/agentbook-ab/harness/tests/ experiments/agentbook-ab/memory/tests/ experiments/agentbook-ab/pipeline/tests/ -q` must pass at the end of every code batch.

## Environment Notes

- Ollama present; not used during code-only batches.
- `claude` CLI v2.1.153.
- `_oracle/outcomes_log.json` exists; unit tests use `tmp_path`.

## Blockers

None for code work. Operator-deferred: 004, 007, 016.
