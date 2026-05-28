# Batching Strategy

Three subsystems ship as **pre-flight + three sequential batches**, each with quantitative entry and exit gates. A later batch only starts after the prior gate passes; each batch is an independently shippable change, so deferring or dropping a later batch wastes no prior effort.

The point of mid-batch testing is **not** pass/fail bookkeeping — it is to surface *what to change next*. Each exit gate produces measurements that either confirm the next batch's hypothesis or invalidate it, so we don't ship a fix to a problem the previous batch already solved.

## Pre-flight — token-cap baseline (~30 minutes)

The cheapest possible probe of the 15976 truncation hypothesis. If raising the token cap alone unsticks 15976, Batch 1's parser fix is still worth shipping (other models / fence variants) but its bar drops from "unstick a task" to "no regression + cleaner notes".

**Change**: `harness/llm_ollama.py:54` — `max_tokens=8000` → `max_tokens=16000`.

**Run**: `uv run python -m pipeline.orchestrator --only sympy__sympy-15976 --arms good good_synth good_loop good_multi_loop -k 3 --workers 1` against gemma4_e4b. Archive results to `runs_v2.preflight/`.

**Measurements** (written to `runs_v2.preflight/SUMMARY.md`):

| Metric | How |
|---|---|
| `truncated_no_block_notes_pre/post` | grep `episode.notes` for `"```edit"` substring in entries beginning with `no-block` |
| `15976_resolved_post` | any cell on 15976 has `resolved=True` |
| `mean_turns_used_pre/post` | average across all 12 cells (4 arms × 3 samples) |

**Decision branches**
- **Branch A**: 15976 resolves AND `truncated_no_block_notes_post ≈ 0` — token cap was the dominant cause. Adjust Batch 1's exit gate 5 from "K_post ≥ K_pre" to "K_post = K_pre" and proceed.
- **Branch B**: 15976 still fails OR no-block notes persist — parser fix is the right tool, proceed as planned.
- **Branch C**: 15976 resolves but no-block notes persist — token cap helped but other failures remain; parser still needed. Proceed.

Pre-flight is reversible: revert the one-line change before starting Batch 1 to preserve a clean baseline for Batch 1's own measurements (decided per branch: A keeps the higher cap, B/C revert).

## Batch 1 — Lenient Edit Parser (Subsystem 2)

Smallest, most isolated, no Opus calls, no schema changes, all changes confined to `harness/`.

**Files**: `harness/prompts.py`, `harness/agent_loop.py`, `harness/tests/test_search_replace.py`.

**Entry gate**: Pre-flight measurements recorded; pre-flight branch decision applied to the gate-5 threshold.

**Exit gate** (full 17-task gemma4_e4b suite, 4 runtime arms, k=3):

| # | Check | Threshold |
|---|---|---|
| 1 | All unit tests pass | 26/26 (15 existing + 11 new) |
| 2 | Truncated-edit notes drop | `truncated_no_block_notes_post ≤ 0.2 × pre` |
| 3 | Doom-loop episodes drop | `doom_loop_episodes_post == 0` (no episode with ≥ 4 consecutive identical-prefix unparseable-edit turns) |
| 4 | No regression | `regression_count == 0` (every task resolved pre-Batch-1 still resolves) |
| 5 | Union holds or grows | `K_post ≥ K_pre` (or `K_post == K_pre` under pre-flight Branch A) |

**Optimization signals exposed** (record in `runs_v2.batch1/SUMMARY.md`):
- Per-arm pass@3 delta. If gemma's `good_loop` improves but `good_multi_loop` does not, the doom-loop fix's leverage is arm-specific — informs whether `good_rotate` later needs arm-specific weights.
- Distribution of `diagnose_edit_block(text)` outcomes across the suite. If "missing closing triple-backtick" dominates, the underlying truncation class is what we hypothesized; if "missing ======= separator" appears, that's a new class to test for.
- Per-iid `notes`-count delta. Tasks where notes drop sharply but `resolved` stays False are candidates for Batch 2 cue refinement.

If gate 5 is negative: stop and root-cause. The lenient fallback is probably applying a wrong edit silently — inspect the iids that regressed against the recovered-tuple log.

If gates 1-4 pass but gate 5 is flat: parser cleaned the protocol but the model still cannot land the fix once given clean feedback. Document as "infrastructure improvement, behavior-neutral" and proceed to Batch 2 — clean feedback is a precondition for refined cues to teach anything.

## Batch 2 — Outcome-Driven Cue Refinement (Subsystem 1)

Medium cost (Opus calls), medium risk (writes new knowledge artifacts that downstream arms consume).

**Files**: `memory/refine_from_outcomes.py` (new), `_oracle/synth_cache.json` (schema-extended), `pipeline/arm_context.py:_synth_entry`, `memory/tests/test_refine_from_outcomes.py` (new).

**Entry gate**:
1. Batch 1 exit gate passed and recorded.
2. `select_stuck(model_slug="gemma4_e4b", min_failure_count=3)` returns ≥ 1 iid. (Empty list ⇒ Batch 1 already solved everything ⇒ Batch 2 has nothing to refine ⇒ defer.)
3. Pre-Batch-2 `K_pre` recorded explicitly so the recovery-rate denominator is unambiguous.

**Exit gate** (refined iids first, then full 17-task suite for regression check):

| # | Check | Threshold |
|---|---|---|
| 1 | All refinement unit tests pass | 10/10 |
| 2 | Leak audit | `leak_lines_removed == 0` for ≥ 80 % of refined entries; any value ≥ 3 triggers a prompt audit before merge |
| 3 | **HARD gate** — no regression | `regression_count == 0`; enforced in code by `refine_from_outcomes.py --require-no-regression` (default on) which exits non-zero AND leaves top-level aliases pointing to the prior revision until resolved |
| 4 | Stuck-task recovery | `(K_post − K_pre) / (17 − K_pre) ≥ 0.25` (unstick at least 1 of the 2 currently-stuck tasks) |
| 5 | Cost telemetry | Per-revision elapsed_s median ≤ 60 s; total Opus wall time and request count logged to `refine_from_outcomes.log` |

**Optimization signals exposed**:
- For each refined iid, the diff between `revisions[0].localization_cues` and `revisions[1].localization_cues`. Cluster the kinds of edits Opus makes — "enumerated call sites", "added precondition", "narrowed pattern". Whichever cluster correlates with recovery should become an explicit prompt instruction in the next iteration.
- `failure_evidence_count` vs recovery outcome. If recovery only happens when `failure_evidence_count ≥ 6`, raise the `min_failure_count` default; if recovery happens at 3 already, the floor is right.
- Which arm now resolves the refined task. If `good_loop` consistently wins on refined tasks but `good` does not, refinement is amplifying loop-style arms — informs Batch 3 routing.

If gate 4 misses (< 0.25 recovery): the cue-specificity hypothesis is partially or wholly invalidated. **Do not proceed to Batch 3.** Inspect refined cues vs failure evidence by hand; the answer is either "the cues are right but the model is at its ceiling" (in which case the work is done at this model size) or "the cues are still too abstract" (in which case the refinement prompt itself needs revising — that's the next task).

## Batch 3 — Adaptive Sample Rotation (Subsystem 3, *conditional*)

Only triggered if Batch 2 produced a non-trivial mixed-outcome surface for rotation to act on. The original design noted that rotation cannot help when every arm gives the same answer on a task — the 5-arm union of 15/17 means 2 tasks have 0-of-5 and 15 have ≥1-of-5, both of which are rotation-trivial. Batch 2's job is to convert the 0-of-5 tasks into mixed-outcome tasks; only then does rotation have leverage.

**Files**: `pipeline/router.py`, `pipeline/arm_context.py`, `pipeline/orchestrator.py`, `pipeline/tests/test_router.py` (new).

**Entry gate**:
1. Batch 2 exit gate passed.
2. Post-Batch-2 outcomes log contains ≥ 1 iid where two or more runtime arms differ on `resolved` for the same `(iid, model_slug)`. This is the structural precondition for rotation to do anything.
3. Offline simulation: `evaluate_offline_rotate(RuleRouter(), k=3)` reports `coverage_rotate > coverage_best_static_arm` by ≥ 1 task under LOO on the post-Batch-2 log.

If any entry gate fails: ship Batches 0–2 alone and record Batch 3 as deferred with the specific failing gate. The two surviving subsystems are a complete, defensible result; rotation needs a larger / more diverse task population to demonstrate value and that population doesn't exist yet.

**Exit gate**:

| # | Check | Threshold |
|---|---|---|
| 1 | All rotation tests pass | 13/13 (5 in-trial + 3 offline-eval + 5 router unit) |
| 2 | Online lift | `K_rotate ≥ K_best_static_arm` on the post-Batch-2 task set |
| 3 | No regression | `regression_count == 0` against the post-Batch-2 baseline |

## Cross-batch invariants

- **Each batch is its own commit** (or PR). The git history reads as a sequence of independently-revertable steps, not one mega-merge.
- **Outcomes log is the single source of truth for K_pre/K_post computations.** All gate numbers come from `_oracle/outcomes_log.json`, never from ad-hoc grepping of `runs_v2/`.
- **`runs_v2/` archival convention**: `runs_v2.preflight/`, `runs_v2.batch1/`, `runs_v2.batch2/`, `runs_v2.batch3/`. Each archive is read-only after its batch closes; subsequent batches write to a fresh `runs_v2/`.
- **Gate measurements are written to `SUMMARY.md` files inside each archive.** A future retrospective reads them as-is without re-running anything.
- **Tests at batch boundaries**: `uv run python -m pytest experiments/agentbook-ab/ -q` must pass at the end of every batch. Per-batch unit tests are additive; nothing in a later batch can break an earlier batch's tests.
