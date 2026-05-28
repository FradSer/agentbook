# Handoff State (cumulative cross-batch memory)

**Last updated:** 2026-05-29 (after Batch 2, before Batch 3)

## Completed Task IDs

- 001 (preflight; 4-cell partial; Branch B)
- 002 (lenient parser tests)
- 003 (lenient parser impl)
- 004 (Batch 1 exit gate; OPERATOR-DEFERRED)
- 005 (refinement tests)
- 006 (refinement impl + `_synth_entry` revision-aware reader)
- 007 (Batch 2 exit gate; OPERATOR-DEFERRED)

## Modified Files (accumulated from prior batches)

- `experiments/agentbook-ab/harness/prompts.py` (Batch 1 task 003) — lenient `extract_edits` + `looks_like_edit_intent` + `diagnose_edit_block`.
- `experiments/agentbook-ab/harness/agent_loop.py` (Batch 1 task 003) — `_EDIT_MALFORMED_HINT` + malformed-edit dispatch branch.
- `experiments/agentbook-ab/harness/tests/test_search_replace.py` (Batch 1 task 002) — 11 new tests; 26/26 PASS.
- `experiments/agentbook-ab/harness/llm_ollama.py` (Batch 1 task 001) — Branch B reversion; net diff 0.
- `experiments/agentbook-ab/memory/refine_from_outcomes.py` (Batch 2 task 006) — 880 lines; full CLI (14 flags), `select_stuck`, `harvest_failing_transcripts`, `build_refine_prompt`, `call_opus`, `write_revision`, `--rollback-to-rev N` audit field.
- `experiments/agentbook-ab/memory/tests/__init__.py` (Batch 2 task 005) — empty package marker.
- `experiments/agentbook-ab/memory/tests/test_refine_from_outcomes.py` (Batch 2 task 005) — 10 tests; all PASS.
- `experiments/agentbook-ab/pipeline/arm_context.py` (Batch 2 task 006) — `_synth_entry` revision-aware merged view; backwards-compat preserved.

## Recurring Failure Patterns

None detected through Batches 1-2.

## Key Architectural Decisions Carried Forward

- **Preflight Branch B:** `max_tokens=8000` (reverted). Truncation class is fully eliminated by the parser fix; 15976 requires Batch 2's cue refinement (already shipped, awaiting operator sweep at task-007 for empirical validation on real Ollama runs).
- **Anti-leak contract (defense in depth)** for refinement: three-layer filter — `harvest_failing_transcripts` filters tests/gold; `build_refine_prompt` re-validates pre-return; `write_revision` runs `scrub_leak`. `leak_lines_removed` recorded per revision.
- **Comparison protocol gate plumbed via `mirror_aliases`:** `write_revision` keeps top-level aliases pointing at prior revision when `--require-no-regression` would otherwise fire. New revision still persisted under `revisions` for inspection.
- **`_extract_json` reused via direct import from `memory.synthesize`** (no `memory/_claude_io.py` refactor needed).
- **Per-batch commit invariant maintained:**
  - Batch 1 = `d4e94f4` (`feat(agent): implement lenient edit parser`)
  - Batch 2 = `8f56528` (`feat(agent): implement cue refinement`)
- **`pipeline/arm_context.py:_synth_entry` revision-aware reader is live.** Existing arms (`good`, `good_synth`, `good_loop`, `good_multi_loop`, `good_router`) read refined cues automatically once a `revisions` list is present on an entry; alias contract makes this transparent.
- **`pipeline.router._ACTIVE_ROUTER` module-level global** is the swap point: setting `set_router(KNNRouter())` is enough to flip rotation policy for the `good_rotate` arm to be added in Batch 3.
- **TaskList ops tasks marked completed-deferred:** 004, 007 already marked; 016 will be marked at Batch 3 close. Operator runs the sweeps when wall-time is available; SUMMARY.md commands documented in handoff-summary-1.md / handoff-summary-2.md / Batch 3's handoff-summary-3.md.

## Cross-Batch Invariants (per design `_index.md`)

- Each batch is its own commit.
- `_oracle/outcomes_log.json` is the single source of truth for `K_pre`/`K_post`.
- `runs_v2/` archival convention: `runs_v2.preflight/`, `runs_v2.batch1/`, `runs_v2.batch2/`, `runs_v2.batch3/`.
- All gate measurements in `SUMMARY.md` inside each archive.
- `uv run python -m pytest experiments/agentbook-ab/harness/tests/ experiments/agentbook-ab/memory/tests/ experiments/agentbook-ab/pipeline/tests/ -q` must pass at the end of every code batch (Batch 3 adds the pipeline test package).

## Environment Notes

- Ollama running; gemma4:e4b + gpt-oss:20b pulled. (Not used during code-only batches.)
- `claude` CLI v2.1.153 on PATH.
- `_oracle/outcomes_log.json` exists from prior experiment runs (pre-Batch-1 state). Unit tests use `tmp_path` fixtures — production data files are read-only.

## Blockers

None for code work. Wall-time blocks operator-deferred ops tasks (004/007/016).
