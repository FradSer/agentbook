# Task 001: Pre-flight token-cap baseline

**depends-on**: (none)

## Description

Probe the cheapest possible explanation for the `sympy__sympy-15976` failure class before investing in the parser fix: raise `harness/llm_ollama.py:54` from `max_tokens=8000` to `max_tokens=16000`, run a focused gemma4_e4b sweep on the suspected task, write `runs_v2.preflight/SUMMARY.md` with three measurements, and pick a Batch-1 gate-5 threshold based on the result (per [batching-strategy.md](../2026-05-27-agentbook-outcome-loop-design/batching-strategy.md) "Pre-flight" Branch A/B/C decision tree).

This is a config-and-measurement task — no behavioural feature, no BDD scenario. Its output is the choice of `K_post ≥ K_pre` vs `K_post == K_pre` for task-004's exit-gate row 5, plus the empirical confirmation/rejection of the "truncation = pure token-cap problem" hypothesis.

## Execution Context

**Task Number**: 001 of 016
**Phase**: Pre-flight (Batch 0)
**Prerequisites**:
- Local Ollama with gemma4:e4b pulled and reachable.
- A clean `_oracle/outcomes_log.json` regenerated against the current `runs_v2/` so `K_pre` is well-defined.
- The current `runs_v2/` archived (or emptied) so the pre-flight run does not collide with prior cells.

## BDD Scenario

```gherkin
# Setup/measurement task — no Gherkin scenario in bdd-specs.md.
# Covered under _index.md "Tasks without direct BDD mapping" per PLAN-BDD-03.
# Acceptance is the operator-readable runs_v2.preflight/SUMMARY.md with the
# three measurements below filled in and the chosen branch (A/B/C) recorded.
```

**Spec Source**: [batching-strategy.md "Pre-flight — token-cap baseline"](../2026-05-27-agentbook-outcome-loop-design/batching-strategy.md)

## Files to Modify/Create

- Modify: `experiments/agentbook-ab/harness/llm_ollama.py:54` — change `max_tokens=8000` to `max_tokens=16000`.
- Create: `experiments/agentbook-ab/runs_v2.preflight/SUMMARY.md` (operator-authored, archive metadata).
- Read-only: `_oracle/outcomes_log.json`, `runs_v2.preflight/<cell-dirs>/transcript.json`.

## Steps

### Step 1: Capture pre-change baseline measurements
- From the current `runs_v2/` (or, if already cleared, from `_oracle/outcomes_log.json`), record `K_pre = 15` for gemma4_e4b on the 17-task hard sympy subset.
- Count `truncated_no_block_notes_pre`: grep `runs_v2/sympy__sympy-15976__*gemma4_e4b__s*/transcript.json` for `episode.notes` entries whose body begins with `no-block` and contains the substring `` ```edit ``. Record the count and the per-cell distribution.
- Record `mean_turns_used_pre`: average across the 12 gemma4_e4b cells (4 runtime arms × 3 samples) on 15976.

### Step 2: Apply the one-line config change
- Edit `experiments/agentbook-ab/harness/llm_ollama.py:54`: `max_tokens=8000` → `max_tokens=16000`.
- Verify no other call site reads `max_tokens` as a literal 8000.

### Step 3: Re-run gemma4_e4b on 15976
- Run: `uv run python -m pipeline.orchestrator --only sympy__sympy-15976 --arms good good_synth good_loop good_multi_loop -k 3 --workers 1`.
- Wait for all 12 cells to complete; do not parallelize cells (workers=1 keeps the measurement clean).
- Archive: `mv runs_v2 runs_v2.preflight`.

### Step 4: Compute post-change measurements
- `truncated_no_block_notes_post`: same grep as Step 1 against `runs_v2.preflight/`.
- `15976_resolved_post`: boolean — `True` iff any of the 12 cells has `result.json:resolved == true`.
- `mean_turns_used_post`: average across the 12 cells.

### Step 5: Write `runs_v2.preflight/SUMMARY.md`
- Include the three measurements above with `_pre` / `_post` columns.
- Pick exactly one of the three branches and record the decision verbatim:
  - **Branch A** — `15976_resolved_post == True` AND `truncated_no_block_notes_post ≈ 0`: token cap was dominant; Batch 1 gate-5 threshold becomes `K_post == K_pre`; record "keep `max_tokens=16000`".
  - **Branch B** — `15976_resolved_post == False` OR `truncated_no_block_notes_post > 0`: parser fix is required; record "revert `max_tokens` to 8000 before Batch 1".
  - **Branch C** — `15976_resolved_post == True` but `truncated_no_block_notes_post > 0`: token cap helped but failure modes remain; parser still needed; record "revert `max_tokens` to 8000 before Batch 1".

### Step 6: Apply branch-specific reversion
- Under Branch B or C: revert `harness/llm_ollama.py:54` to `max_tokens=8000`. Under Branch A: leave at `16000`.
- Note the final state in `SUMMARY.md`.

## Verification Commands

```bash
# Confirm the one-line config change took effect
grep -n "max_tokens" experiments/agentbook-ab/harness/llm_ollama.py

# Run the focused sweep
cd experiments/agentbook-ab && \
  uv run python -m pipeline.orchestrator --only sympy__sympy-15976 \
    --arms good good_synth good_loop good_multi_loop -k 3 --workers 1

# Inspect cell outcomes
ls runs_v2.preflight/sympy__sympy-15976__*gemma4_e4b__s*/result.json | \
  xargs -I{} jq '{cell: input_filename, resolved: .resolved}' {}

# Count truncated-no-block notes (pre vs post)
grep -l "no-block.*\`\`\`edit" runs_v2.preflight/sympy__sympy-15976__*gemma4_e4b__s*/transcript.json | wc -l
```

## Success Criteria

- `harness/llm_ollama.py:54` is in the branch-specified terminal state (`16000` for A; `8000` for B or C).
- `runs_v2.preflight/SUMMARY.md` exists and records: `truncated_no_block_notes_pre/post`, `15976_resolved_post`, `mean_turns_used_pre/post`, chosen branch letter (A/B/C), and the Batch-1 gate-5 threshold to use (`K_post ≥ K_pre` or `K_post == K_pre`).
- `runs_v2.preflight/` is read-only (archived); a fresh empty `runs_v2/` is staged for Batch 1.
- A short operator note in `SUMMARY.md` cites the corresponding [batching-strategy.md](../2026-05-27-agentbook-outcome-loop-design/batching-strategy.md) branch.
