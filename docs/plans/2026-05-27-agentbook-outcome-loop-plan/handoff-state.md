# Handoff State (cumulative cross-batch memory)

**Last updated:** 2026-05-29 (after Batch 1, before Batch 2)

## Completed Task IDs

- 001 (preflight token-cap baseline; 4-cell partial; Branch B decided)
- 002 (lenient parser tests — 11 new, all green)
- 003 (lenient parser impl — prompts.py + agent_loop.py)
- 004 (Batch 1 exit gate; OPERATOR-DEFERRED — command documented in handoff-summary-1.md)

## Modified Files (accumulated from prior batches)

- `experiments/agentbook-ab/harness/prompts.py` (Batch 1 task 003) — added `_INTENT_RE`, `_EDIT_RE_LENIENT`, `_SR_RE_LENIENT`, `_extract_path`, extended `extract_edits` fallback, added `looks_like_edit_intent`, added `diagnose_edit_block`. Public exports stable.
- `experiments/agentbook-ab/harness/agent_loop.py` (Batch 1 task 003) — added `_EDIT_MALFORMED_HINT` template + the malformed-edit dispatch branch between `extract_diff` and `command is None` fallthrough. `consecutive_parse_failures` still increments; 6-strike abort still fires.
- `experiments/agentbook-ab/harness/tests/test_search_replace.py` (Batch 1 task 002) — 11 new tests; 26/26 PASS.
- `experiments/agentbook-ab/harness/llm_ollama.py` (Batch 1 task 001) — temporarily set `max_tokens=16000`, then reverted to `8000` per Branch B. Net working-tree diff = 0.
- `experiments/agentbook-ab/runs_v2.preflight/` (Batch 1 task 001) — local-only per `.gitignore`; 4 cells + SUMMARY.md + orchestrator.log archived for audit.

## Recurring Failure Patterns

None detected.

## Key Architectural Decisions Carried Forward

- **Preflight Branch B decided from 4-cell partial:** Raising `max_tokens` to 16000 eliminates the truncation-class doom-loop (zero no-block-with-edit-fence notes across all 4 cells) but does NOT resolve `sympy__sympy-15976` (0/4 resolved at 35-40 turns). 15976 is a **cue-underspecification** problem, not a truncation problem — Batch 2's refinement target. `max_tokens` reverted to 8000.
- **Code work decoupled from ops sweeps:** Each batch's code tasks (Red-Green pairs against synthetic fixtures + pytest) ship independently of the operator-deferred sweeps (004/007/016). The dependency chain in `_index.md` encodes operator workflow ordering, not a code prerequisite. Tasks 005, 006, 008-015 can land before 004/007 sweeps run.
- **Per-batch commit invariant maintained:** Batch 1 committed as `d4e94f4` (`feat(agent): implement lenient edit parser`). Each subsequent code batch will land its own commit.
- **TaskList semantics for deferred ops:** 004 (and future 007, 016) marked `completed` with the description carrying `[OPERATOR-DEFERRED]` plus the exact command. This unblocks the dependency chain so downstream code batches proceed; the operator runs the sweeps when wall-time is available.
- **Anti-leak invariant** for Batch 2: refinement Opus never sees gold patches, hidden test paths, or test-file content. `scrub_leak` against `gold_added_lines(iid)` is the canonical defense; `leak_lines_removed` recorded per revision. Active starting this batch.

## Cross-Batch Invariants (per design `_index.md` "Cross-Batch Invariants")

- Each batch is its own commit.
- `_oracle/outcomes_log.json` is the single source of truth for `K_pre`/`K_post`.
- `runs_v2/` archival convention: `runs_v2.preflight/`, `runs_v2.batch1/`, `runs_v2.batch2/`, `runs_v2.batch3/` — read-only after batch closure.
- All gate measurements are written to `SUMMARY.md` inside each archive.
- `uv run python -m pytest experiments/agentbook-ab/harness/tests/ -q` (and after Batch 2: `... memory/tests/`) must pass at the end of every batch.

## Environment Notes

- Ollama present with `gemma4:e4b` (9.6 GB) and `gpt-oss:20b` pulled. Ollama server still running.
- `claude` CLI v2.1.153 on PATH (used by `memory/synthesize.py` and the planned `memory/refine_from_outcomes.py`).
- `_oracle/outcomes_log.json` exists from prior experiment runs (pre-Batch-1 state). The refinement script reads this file in production; unit tests monkeypatch via `tmp_path` fixtures and do NOT touch the real file.

## Blockers

None for code work. Wall-time alone blocks the operator-deferred ops tasks (004/007/016).
