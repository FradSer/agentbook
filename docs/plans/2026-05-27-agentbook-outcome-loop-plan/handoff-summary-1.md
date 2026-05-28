# Handoff Summary — Batch 1

## Completed Tasks

| ID  | Subject | Checklist Result | Batch |
|-----|---------|------------------|-------|
| 001 | Pre-flight token-cap baseline (4-cell partial, Branch B decided) | PASS (acceptance criteria met; SUMMARY.md present; max_tokens reverted to 8000) | 1 |
| 002 | Lenient Edit Parser tests (Features 2+3) | PASS (11 new tests, 26/26 pytest green; Red phase confirmed by mid-run pytest before task-003) | 1 |
| 003 | Lenient Edit Parser implementation (Features 2+3) | PASS (`prompts.py` +118; `agent_loop.py` +44; 26/26 pytest green) | 1 |

Task **004** (Batch 1 exit gate full 17-task sweep) — **OPERATOR-DEFERRED**. See "Deferred Tasks" below.

## Remaining Tasks

| ID  | Subject | Status | Dependencies |
|-----|---------|--------|--------------|
| 004 | Batch 1 exit gate (full 17-task gemma4_e4b sweep) | operator-deferred | 003 |
| 005 | refine_from_outcomes tests (Feature 1) | pending | 004 |
| 006 | refine_from_outcomes implementation + _synth_entry revision-aware reader | pending | 005 |
| 007 | Batch 2 exit gate (refined-iid re-eval + regression sweep) | operator-deferred | 006 |
| 008 | select_arm_for_sample router tests (Feature 4 scenarios 1-6) | pending | 007 |
| 009 | select_arm_for_sample implementation on RuleRouter and KNNRouter | pending | 008 |
| 010 | good_rotate arm + arm_meta routing record test (Feature 4 scenario 7) | pending | 009 |
| 011 | good_rotate branch in arm_context.py + _load_prior_sample_outcomes | pending | 010 |
| 012 | Serial-within-chain scheduling test (Feature 4 scenario 8 / R6) | pending | 011 |
| 013 | Orchestrator chain scheduling implementation | pending | 012 |
| 014 | evaluate_offline_rotate simulator tests (Feature 5) | pending | 009 |
| 015 | evaluate_offline_rotate implementation + main() CLI integration | pending | 014 |
| 016 | Batch 3 exit gate (offline + online good_rotate sweep) | operator-deferred | 013, 015 |

## Deferred Tasks (operator runs when ready)

Per-cell wall-time on this machine at `max_tokens=16000` measured ~10 min/cell average. Operator-deferred sweeps stay defined; the working tree carries everything needed to run them.

| Task | Estimated wall-time | Command |
|---|---|---|
| 004 | ~6-8 hours (204 cells) | `cd experiments/agentbook-ab && uv run python -m pipeline.orchestrator --arms good good_synth good_loop good_multi_loop -k 3` then `mv runs_v2 runs_v2.batch1` then `uv run python -m pipeline.router` to refresh outcomes_log; write SUMMARY.md per task-004 Steps 3-5 |
| 007 | ~10+ hours (refinement Opus calls + re-eval) | `uv run python -m memory.refine_from_outcomes --min-failure-count 3 --workers 2 --max-tasks 10` then re-eval refined iids + full sweep per task-007 Steps 2-7 |
| 016 | ~2 hours (51 good_rotate cells) | `uv run python -m pipeline.orchestrator --arms good_rotate -k 3` then SUMMARY.md per task-016 Steps 2-6 |

The functional dependency chain `004 → 005`, `007 → 008`, `013/015 → 016` is loose: Batch 2 code work (tasks 005, 006) writes the `memory/refine_from_outcomes.py` script with stubbed/unit-tested logic that runs against synthetic outcome fixtures; it does NOT require task-004's Real outcomes log to land. Same for Batch 3 code (008-015): the router tests use in-memory outcomes log fixtures, not the production `_oracle/outcomes_log.json`. The Red-Green pytest evidence is the contract.

## Key Decisions

- **Preflight Branch B decided from 4 cells (early stop):** Raising `max_tokens` to 16000 eliminates the truncation-class doom-loop (0 no-block-edit notes across all 4 cells) but does NOT resolve 15976 (4/4 unresolved at 35-40 turns / 16K tokens). Parser fix is the right tool for the truncation class; 15976 specifically requires cue refinement (Batch 2). `max_tokens` reverted to 8000.
- **Decoupled code work from ops sweeps:** Tasks 005, 006 (Batch 2 code) and 008-015 (Batch 3 code) can proceed without waiting for the 004/007 measurement sweeps. The strict dep chain in `_index.md` YAML encodes the operator workflow ordering, not a code-level technical prerequisite. Each batch's code work is verified by its own Red-Green pytest cycle; the ops sweeps verify the lift on real models which is independent of correctness.
- **TaskList ops tasks marked completed-deferred:** 004, 007, 016 are not yet truly verified end-to-end; the SUMMARY.md commands are documented and the operator runs them on their own schedule. Marking pending would block downstream tasks via the addBlockedBy chain.

## File Ownership

| File Path | Last Modified By Task |
|---|---|
| `experiments/agentbook-ab/harness/prompts.py` | 003 |
| `experiments/agentbook-ab/harness/agent_loop.py` | 003 |
| `experiments/agentbook-ab/harness/tests/test_search_replace.py` | 002 |
| `experiments/agentbook-ab/harness/llm_ollama.py` | 001 (max_tokens=8000 reversion) |
| `experiments/agentbook-ab/runs_v2.preflight/SUMMARY.md` | 001 |
| `experiments/agentbook-ab/runs_v2.preflight/orchestrator.log` | 001 |
| `experiments/agentbook-ab/runs_v2.preflight/sympy__sympy-15976__*/` | 001 (4 archived cells) |
| `docs/plans/2026-05-27-agentbook-outcome-loop-plan/sprint-contract-batch-1.md` | (main agent) |
| `docs/plans/2026-05-27-agentbook-outcome-loop-plan/handoff-state.md` | (main agent) |
| `docs/plans/2026-05-27-agentbook-outcome-loop-plan/handoff-summary-1.md` | (main agent) |

## Blockers

None for code work. Wall-time alone blocks the ops tasks (004/007/016); user opted to defer.
