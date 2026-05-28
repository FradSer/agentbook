# Handoff State (cumulative cross-batch memory)

**Last updated:** 2026-05-29 (before Batch 1)

## Completed Task IDs

None yet — Batch 1 has not started.

## Modified Files (accumulated from prior batches)

None.

## Recurring Failure Patterns

None detected (no prior evaluation reports).

## Key Architectural Decisions Carried Forward

- **Strict dependency chain in plan** (`_index.md` YAML): 001 → 002 → 003 → 004 → ... → 016. Functional reality is more permissive — task-002 (writing Red tests against a stable contract from architecture.md) does NOT actually depend on task-001's measurement output; the chain encodes batching-strategy ordering. The coordinator MAY launch task-001's background eval and execute task-002+003 in parallel to it, then wait for task-001 results before task-004. Document any deviation from the chain in the per-batch sprint contract.
- **Anti-leak invariant** for Batch 2 onward: refinement Opus never sees gold patches, hidden test paths, or test file content. `scrub_leak` against `gold_added_lines(iid)` is the canonical defense; `leak_lines_removed` recorded per revision. Not active in Batch 1.
- **`max_tokens` config in `harness/llm_ollama.py:54`** is the orthogonal complementary lever to the parser fix; task-001's pre-flight chooses Branch A/B/C which sets Batch-1 gate-5 threshold and the final value of `max_tokens`.
- **Batching strategy load-bearing** (`batching-strategy.md`): each batch has explicit entry/exit gates; later batches may be deferred without sunk effort if earlier batches already cover their target. Batch 3 in particular is conditional on Batch 2 producing a mixed-outcome surface for rotation to act on.

## Cross-Batch Invariants (per design `_index.md` "Cross-Batch Invariants")

- Each batch is its own commit.
- `_oracle/outcomes_log.json` is the single source of truth for `K_pre`/`K_post`.
- `runs_v2/` archival convention: `runs_v2.preflight/`, `runs_v2.batch1/`, `runs_v2.batch2/`, `runs_v2.batch3/` — read-only after batch closure.
- All gate measurements are written to `SUMMARY.md` inside each archive.
- `uv run python -m pytest experiments/agentbook-ab/ -q` must pass at the end of every batch.

## Environment Notes

- Ollama present with `gemma4:e4b` (9.6 GB) and `gpt-oss:20b` pulled.
- `claude` CLI v2.1.153 on PATH (used by `memory/synthesize.py` and the planned `memory/refine_from_outcomes.py` — relevant from Batch 2).
- Project Python env: `uv` workspace per CLAUDE.md.

## Blockers

None.
