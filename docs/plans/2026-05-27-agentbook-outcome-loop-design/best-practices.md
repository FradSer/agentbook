# Best practices: agentbook outcome-feedback loop

Operational and code-quality invariants for the three subsystems. Organized as: anti-leak invariants, performance budget, common pitfalls, comparison protocol.

## Anti-leak invariants (load-bearing)

### Refinement prompt (Outcome-Driven Cue Refinement)

1. **Opus input MUST exclude gold and held-out tests.** The refinement prompt MAY include:
   - `tasks/{iid}/BUG.md` (agent-visible bug report).
   - The current `synth_cache[iid]` active fields (already gold-scrubbed at write time).
   - A failing-turns digest from `runs_v2/{iid}__{arm}__{model_slug}__s*/transcript.json`.

   The digest MUST be filtered:
   - **Drop** any `stdout_tail`/`stderr_tail`/note whose content references a path matching `**/tests/**` or `test_*.py`.
   - **Drop** any line whose stripped form is in `gold_added_lines(iid)`.
   - **Truncate** per-turn observations to ≤ 200 chars (the existing `episode.notes` 300-char cap is the precedent).

   The refinement script MUST NOT read `_oracle/{iid}/gold.patch`, the contents of any `tests/` file under the run repo, hidden grading-test names, or the held-out `FAIL_TO_PASS` list. Enforce by importing `gold_added_lines` only (never `(ORACLE / iid / "gold.patch").read_text()`).

2. **Defense in depth — `scrub_leak` after Opus.** The refined entry runs through `_scrub_entry(refined, gold)` even though Opus never saw gold. The resulting `leak_lines_removed` is stored on the new revision. A non-zero count is a smoke signal but not a hard failure (Opus can coincidentally restate a symbol that overlaps with a gold added-line; the scrubber removes it).

3. **Refined entries pass the same anti-leak contract as the original.** Same `scrub_leak`, same `gold_added_lines(iid)`. No new bypass.

4. **Audit field**: every refinement records `leak_lines_removed` on the new revision. If a future audit finds the count consistently > 0 for a class of tasks, that's a signal to tighten the prompt (not to relax the scrubber).

### Parser (Lenient Edit Parser)

5. **The parser is knowledge-agnostic.** It only manipulates the assistant's reply text. It opens no new files, makes no network/subprocess calls, introduces no new shell quoting, and changes no path-handling logic in the applier.

6. **Test-file refusal stays in `apply_search_replace`.** The lenient parser MUST NOT pre-filter or bypass `"/tests/" in f"/{rel}"` and `Path(rel).name.startswith("test_")` checks. Any tuple the lenient parser recovers passes through that gate unmodified. The end-to-end test "test-file refusal still fires for a recovered (unfenced) block" pins this.

7. **No phantom file paths.** If the recovered path line is empty after `strip("`").strip("`#* ").rstrip(":")`, skip the block. The last-resort raw-marker recovery requires a plausible `.py`/`.pyx`/`.pyi` filename with at least one `/` in the preceding 4 lines.

### Outcomes log + adaptive rotation

8. **Outcomes log is read-only during refinement and adaptive sampling.** `refine_from_outcomes.py` and `select_arm_for_sample` only read the log; only the orchestrator's post-cell `update_from_outcome` writes.

9. **Sample-level dedup key**: `(model_slug, iid, arm, sample_idx)` — preserved from current behavior. Last write wins.

10. **Size bound**: at the current 17 iids × 4 runtime arms × 2 models × k ≤ 3 = ≤ 408 rows (~50 KB). Add a soft guard `if len(rows) > 50_000: raise RuntimeError(...)` in `bootstrap_outcomes_log` for future scale. No log rotation needed at this scale.

## Performance budget

### Refinement script

- ThreadPoolExecutor matches `memory/synthesize.py`'s pattern: per-task try/except wrapping the entire Opus call; single `threading.Lock` brackets the atomic `SYNTH_CACHE.write_text(json.dumps(...))`.
- Default `--workers 2` (Opus is slow; 4+ risks rate limits). Operator can raise.
- Default `--timeout 360` (Opus on this prompt should comfortably finish in 20-60s; 360s tolerates spikes).
- `--max-tasks 10` default cap per batch — production rollout should run refinement on a cron-style schedule, not on every report.
- Idempotency: a task is "to-do" iff `failures(model, iid) ≥ min_failure_count` AND `len(revisions) == 1 OR --redo`.

### Lenient parser

- Fast path unchanged: `_EDIT_RE.findall(text)` + `_SR_RE.finditer(block)`. O(text) allocation.
- Fallback branch enters ONLY when fast path returned [] AND `_INTENT_RE.search(text)` matched (cheap substring guard).
- At most one extra `findall` (`_EDIT_RE_LENIENT`) and one re-match (`_SR_RE_LENIENT.finditer`) per message. No per-character work.
- Worst case O(text). On typical short replies (< 4 KB), submillisecond.

### Adaptive Sample Rotation

- `select_arm_for_sample` is O(1) per call after `self.select(...)`'s existing O(|outcomes|) load. No new scans of the log per sample.
- `_load_prior_sample_outcomes` does a directory scan of at most `sample_idx` cell directories (≤ 2 at k=3). Negligible.
- Orchestrator chain scheduling: `args.workers` bounds concurrent chains, not concurrent samples. With 17 stuck-eligible tasks × k=3 and `--workers 12`, total wall time = ceil(17/12) × 3 × sample_latency vs the existing flat ceil(17×3/12) × sample_latency. Small loss; acceptable.

### Test suite

- Total wall time ≤ 2s (current ~1.5s). All new tests use stdlib + `tmp_path` + monkeypatching of `subprocess.run` for refinement; no real Opus calls.
- 11 new parser tests + 5 new rotation tests + 10 new refinement tests = 26 new tests. Target per-test budget: < 50 ms each.

## Common pitfalls — forbidden

1. **Don't let refinement leak failing-transcript paths into cues.** The model would chase phantom file names. Allowlist: only paths matching `*.py`/`*.pyx`/`*.pyi` AND existing in the source tree of the run repo are eligible to surface in the digest. Hidden test paths are filter-dropped before assembly.

2. **Don't let the lenient parser accept "edit" blocks pointed at test files.** The existing refusal in `apply_search_replace` (`"/tests/" in f"/{rel}"` + `Path(rel).name.startswith("test_")`) is the gate. The parser fix MUST NOT pre-filter (it shouldn't have to) and MUST NOT post-filter to bypass it.

3. **Don't let adaptive sampling oscillate.** The `_pick_unexplored` algorithm guarantees termination: each call either returns a never-tried arm (advances) or hits BURN_REPLAY (terminates). With `RUNTIME_ARMS` of size 4 and `k ≤ 4`, BURN_REPLAY only triggers if every arm has at least one observed failure for this task. Operator should set k ≤ |RUNTIME_ARMS| (= 4) in practice.

4. **Don't blur the per-revision lineage.** Every refinement appends `revisions[len(revisions)]`, sets `parent_revision = len(revisions) - 1`, fills `created_at` (ISO UTC), `source` (e.g. `"refine_from_outcomes failure-evidence batch 2026-05-27"`), `failure_evidence_count`, `stuck_criterion`, `refined_from` (list of full run dirnames), `change_rationale`. The lineage is the audit surface.

5. **Don't ship without a comparison protocol.** Pre/post refinement results are NOT directly comparable (selection bias: refinement targets the tasks the model already failed on). The fair comparison is:
   - **Absolute**: `K_post / 17` total resolved tasks under refined cues across all arms.
   - **Stuck-task recovery rate**: `(K_post − K_pre) / (17 − K_pre)` — the fraction of previously-stuck tasks that the refined cues unstuck.
   - Both numbers MUST be reported. Never just a delta on the full set.

6. **Don't run refinement concurrently with eval.** The current `_synth_data` global in `pipeline/arm_context.py` is loaded once per process. Running refinement during an eval batch would make the eval see stale cues. Refinement is an OFFLINE step in the operator workflow; document this in `--help` and `_index.md` Operator workflow.

7. **Don't let `good_rotate` cells run in parallel within a `(iid, model)` chain.** Sample N+1 reads sample N's `result.json` from disk; parallel scheduling within a chain races. The orchestrator change must enforce serial-within-chain scheduling.

8. **Don't let the parser silently accept malformed paths.** If `_extract_path` returns "" or a non-`.py`/`.pyx`/`.pyi` name with no `/`, the block is skipped. A stray `<<<<< SEARCH` in prose with a random preceding word must not become a phantom edit.

9. **Don't change the existing `select_arms` signature.** Add `select_arm_for_sample` as a parallel method, not as overloading. Every existing caller of `select_arms` continues unchanged. The `good_router` arm still uses `select_arms`; `good_rotate` uses `select_arm_for_sample`.

10. **Don't let refined verifications drift from the cues.** `refine_from_outcomes` does NOT regenerate `verifications`. If the refined `verification_method` text changes significantly, the operator MUST run `extract_verification.py --redo --only <iid>` as a separate step. Document in CLI `--help`.

## Comparison protocol (for the post-refinement re-eval)

The operator runs (per `_index.md` workflow):

```bash
# Capture pre-refinement state
mv runs_v2 runs_v2.cues_v1

# Refine and re-eval
uv run python -m memory.refine_from_outcomes --min-failure-count 3
uv run python -m memory.extract_verification --redo --only <refined_iids>
uv run python -m pipeline.orchestrator --arms good good_synth good_loop good_multi_loop \
    --only <refined_iids> -k 3
```

Reporting in any post-run summary MUST include:

| Metric | Definition |
|---|---|
| `K_pre` | tasks resolved by any arm × any sample under `revisions[0]` cues (= 15 currently for gemma4_e4b) |
| `K_post` | tasks resolved by any arm × any sample under `revisions[-1]` cues |
| **Absolute** | `K_post / 17` |
| **Stuck-task recovery rate** | `(K_post − K_pre) / (17 − K_pre)` |
| `K_per_arm_post` | per-arm pass@3 under the refined cues for each runtime arm |
| `regression_count` | tasks resolved under `revisions[0]` but unresolved under `revisions[-1]` (expected: 0) |

Any `regression_count > 0` should be investigated before the refined revision is promoted. A `--rollback-to-rev N` flag on `refine_from_outcomes.py` (future) lets operators revert.

## Code quality and style

- All new Python files conform to ruff rules E/F/I/UP/B/SIM, line length 88, double quotes (per project CLAUDE.md).
- All new functions on the path of an eval cell carry a docstring stating: (a) what it returns, (b) any side effect on `synth_cache.json` / `outcomes_log.json` / disk, (c) thread-safety notes when relevant.
- No new external Python dependencies. Existing imports: stdlib + `httpx` (already used by `harness/llm_ollama.py`).
- Match `memory/synthesize.py` and `memory/extract_verification.py` for CLI/argparse style.

## Security notes (recap)

- Subprocess invocation of `claude -p`: `cwd=tempfile.TemporaryDirectory(prefix="agentbook-refine-")` so CLAUDE.md auto-discovery doesn't pick up the project's instructions. `env=_synth_env()` strips provider override env vars (mirrors `memory/synthesize.py`).
- Refinement runs no shell commands beyond `claude -p` and no file writes outside `_oracle/synth_cache.json`.
- The orchestrator's existing `_scrub_env` (strips KEY/TOKEN/SECRET/PASSWORD env vars before running agent bash) is untouched.
