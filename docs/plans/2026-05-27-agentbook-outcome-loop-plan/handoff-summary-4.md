# Handoff Summary — Batch 4 (final code batch)

## Completed Tasks

| ID  | Subject | Checklist Result | Batch |
|-----|---------|------------------|-------|
| 012 | Serial-within-chain scheduling test | PASS — Red on missing `run_chain` symbol; Green 1/1 | 4 |
| 013 | Orchestrator chain scheduling implementation | PASS (after rework round 1) — initial coordinator landed `run_chain` only; remediation closed BATCH4-013-A/B/C with Red-first Green-follow-on tests | 4 |
| 014 | evaluate_offline_rotate simulator tests | PASS — Red on `AttributeError: module 'pipeline.router' has no attribute 'evaluate_offline_rotate'`; Green 3/3 | 4 |
| 015 | evaluate_offline_rotate implementation + main() CLI integration | PASS — `policy=...  k=3  rotation=True` row prints for both routers on both models | 4 |
| 016 | Batch 3 exit gate (offline + online good_rotate sweep) | OPERATOR-DEFERRED | 4 |

## Final pytest

`uv run python -m pytest experiments/agentbook-ab/harness/tests/ experiments/agentbook-ab/memory/tests/ experiments/agentbook-ab/pipeline/tests/ -q` → **50/50 PASS**

Decomposition:
- harness/tests/test_search_replace.py: 26 (15 existing + 11 from Batch 1)
- memory/tests/test_refine_from_outcomes.py: 10 (Batch 2)
- pipeline/tests/test_router.py: 6 (Batch 3) + 3 (Batch 4 task 014) + 1 (Batch 4 remediation BATCH4-013-C) = 10
- pipeline/tests/test_arm_context.py: 1 (Batch 3)
- pipeline/tests/test_orchestrator.py: 1 (Batch 4 task 012) + 2 (Batch 4 remediation BATCH4-013-A/B) = 3

## Remediation Round 1 — Closed

Audit (`evaluation-round-1-batch-4.md`) flagged three acceptance gaps in task-013's initial implementation:

| ID | Issue | Fix |
|---|---|---|
| BATCH4-013-A | `main()` did NOT split `todo` between rotate-chains and parallel pool | New `_dispatch_todo` helper that `main()` delegates to; Red test references the missing symbol → Green after impl |
| BATCH4-013-B | `_has_memory` was a `main()` closure without a `good_rotate` branch | Lifted `_has_memory` to module-level + added `good_rotate` branch (intersection of mem/synth/loop ids); Red AttributeError → Green |
| BATCH4-013-C | `bootstrap_outcomes_log` only scanned active `runs_v2/` and one v1 archive | Extended to iterate `sorted(ROOT.glob("runs_v2.*"))`; Red assertion on missing archived row → Green |

All three lands as Red-first Green-follow-on tests, matching CODE-TEST-03. The earlier audit's lesson — "when impl-side acceptance criteria mention a control-flow split in `main()`, the Red test must cover the dispatch path, not just the underlying primitive" — is filed as a checklist-evolution candidate for the next retrospective.

## Remaining Tasks

None pending. All 16 plan tasks either landed or are explicitly operator-deferred (004, 007, 016).

## Key Decisions (Batch 4)

- **Two-pool scheduler shipped via `_dispatch_todo`:** Pool A (parallel) for non-rotate cells, Pool B (parallel chains, serial within via `run_chain`) for `good_rotate`. `args.workers` caps chain-level concurrency for rotate, cell-level concurrency for non-rotate (matching the existing behaviour).
- **`_has_memory` is now module-level**, allowing the orchestrator's new test (`test_has_memory_good_rotate_branch`) to call it directly. Previous closure usage inside `main()` was a refactor blocker.
- **Archive-aware outcomes log:** `bootstrap_outcomes_log` now glob-scans `runs_v2.*/` directories so KNN training data sees the full lineage across the operator's per-batch archive convention (`runs_v2.preflight/`, `runs_v2.batch1/`, etc.).
- **Offline simulator results (smoke):** for the current `_oracle/outcomes_log.json` snapshot (pre-operator-sweep), rotation coverage = 11/17 (gemma4_e4b) and 10/17 (gpt-oss_20b) with `arms_used=4` per router. Branch 3 entry-gate-3 check (`coverage_rotate > coverage_best_static_arm` by ≥ 1) will be re-run by the operator against the post-Batch-2 outcomes log when task-007 sweep completes.
- **Final code-batch invariant maintained:**
  - Batch 1 = `d4e94f4` (`feat(agent): implement lenient edit parser`)
  - Batch 2 = `8f56528` (`feat(agent): implement cue refinement`)
  - Batch 3 = `913eb22` + `6ec2fbb` (good_rotate arm + router rotation)
  - Batch 4 = (this commit)

## Final File Ownership

| File Path | Last Modified By Task / Batch |
|---|---|
| `experiments/agentbook-ab/harness/prompts.py` | Batch 1 task 003 |
| `experiments/agentbook-ab/harness/agent_loop.py` | Batch 1 task 003 |
| `experiments/agentbook-ab/harness/tests/test_search_replace.py` | Batch 1 task 002 |
| `experiments/agentbook-ab/harness/llm_ollama.py` | Batch 1 task 001 (net diff 0) |
| `experiments/agentbook-ab/memory/refine_from_outcomes.py` | Batch 2 task 006 |
| `experiments/agentbook-ab/memory/tests/__init__.py` | Batch 2 task 005 |
| `experiments/agentbook-ab/memory/tests/test_refine_from_outcomes.py` | Batch 2 task 005 |
| `experiments/agentbook-ab/pipeline/router.py` | Batch 4 task 015 + rework BATCH4-013-C |
| `experiments/agentbook-ab/pipeline/arm_context.py` | Batch 3 task 011 (Batch 2 added `_synth_entry` revision-aware reader) |
| `experiments/agentbook-ab/pipeline/orchestrator.py` | Batch 4 task 013 + rework BATCH4-013-A/B |
| `experiments/agentbook-ab/pipeline/tests/__init__.py` | Batch 3 task 008 |
| `experiments/agentbook-ab/pipeline/tests/test_router.py` | Batch 4 task 014 + rework BATCH4-013-C |
| `experiments/agentbook-ab/pipeline/tests/test_arm_context.py` | Batch 3 task 010 |
| `experiments/agentbook-ab/pipeline/tests/test_orchestrator.py` | Batch 4 task 012 + rework BATCH4-013-A/B |
| `experiments/agentbook-ab/runs_v2.preflight/` | Batch 1 task 001 (local-only per .gitignore) |
| `docs/plans/2026-05-27-agentbook-outcome-loop-plan/sprint-contract-batch-{1..4}.md` | (main agent) |
| `docs/plans/2026-05-27-agentbook-outcome-loop-plan/handoff-state.md` | (main agent; refreshed each batch) |
| `docs/plans/2026-05-27-agentbook-outcome-loop-plan/handoff-summary-{1..4}.md` | (main agent) |
| `docs/plans/2026-05-27-agentbook-outcome-loop-plan/evaluation-round-1-batch-{2,3,4}.md` | (coordinator inline audit) |

## Operator-Deferred Sweeps (full command catalog)

These remain for the operator to run when wall-time is available. All three are documented in their respective task files plus the per-batch handoff summaries.

```bash
# Task 004: Batch 1 exit gate (~6-8h)
cd experiments/agentbook-ab && uv run python -m pipeline.orchestrator \
    --arms good good_synth good_loop good_multi_loop -k 3
mv runs_v2 runs_v2.batch1
uv run python -m pipeline.router  # refresh outcomes_log
# Then write runs_v2.batch1/SUMMARY.md per task-004 Step 3-5

# Task 007: Batch 2 exit gate (~10h+ — Opus refinement + 204+ cell re-eval)
cd experiments/agentbook-ab && uv run python -m memory.refine_from_outcomes \
    --min-failure-count 3 --workers 2 --max-tasks 10 --require-no-regression
# Then re-eval refined iids + full sweep per task-007 Steps 2-7
# Write runs_v2.batch2/SUMMARY.md

# Task 016: Batch 3 exit gate (~2h+ — 51 good_rotate cells)
cd experiments/agentbook-ab && uv run python -m pipeline.router  # confirm entry-gate-3
cd experiments/agentbook-ab && uv run python -m pipeline.orchestrator --arms good_rotate -k 3
mv runs_v2 runs_v2.batch3
uv run python -m pipeline.router  # refresh outcomes_log
# Then write runs_v2.batch3/SUMMARY.md per task-016 Steps 4-6
```

## Blockers

None.

## Plan Status

**All code work landed. Operator workflow documented. Plan execution complete pending operator sweeps.**
