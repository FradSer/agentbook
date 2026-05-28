# evaluation-round-1-batch-2

**Mode:** code
**Sprint contract:** `docs/plans/2026-05-27-agentbook-outcome-loop-plan/sprint-contract-batch-2.md`
**Checklist:** `docs/retros/checklists/code-v1.md`
**Round:** 1
**Date:** 2026-05-29

## Per-Task Verification Commands

| Task | Command | Exit | Last lines |
|------|---------|------|------------|
| 005 (Red, captured pre-006) | `uv run python -m pytest memory/tests/test_refine_from_outcomes.py -q` | non-zero (collection error) | `ImportError: cannot import name 'refine_from_outcomes' from 'memory'` — structural failure naming the missing module, matches CODE-TEST-03 (Red shape per sprint contract). |
| 005 (Green, after 006) | `uv run python -m pytest memory/tests/test_refine_from_outcomes.py -q` | 0 | `10 passed in 0.11s` |
| 006 (scoped sweep) | `uv run python -m pytest harness/tests/ memory/tests/ -q` | 0 | `36 passed in 0.28s` (26 harness + 10 memory) |
| 006 (ruff) | `uv run ruff check experiments/agentbook-ab/memory/refine_from_outcomes.py experiments/agentbook-ab/pipeline/arm_context.py experiments/agentbook-ab/memory/tests/test_refine_from_outcomes.py` | 0 | `All checks passed!` |
| 006 (CLI --help) | `uv run python -m memory.refine_from_outcomes --help` | 0 | All 14 documented flags surfaced (`--only`, `--model-slug`, `--min-failure-count`, `--redo`, `--workers`, `--model`, `--timeout`, `--dry-run`, `--max-tasks`, `--cues-version`, `--require-no-regression`, `--allow-regression`, `--reason`, `--rollback-to-rev`). |
| 006 (CLI --dry-run) | `uv run python -m memory.refine_from_outcomes --dry-run --min-failure-count 3` | 0 | Prints planned task list; zero `subprocess.run` calls (traced); under-evidenced iids gracefully report the gap. |

## Per-Task Checklist Results

### Task 005 (test, Red)

| Item ID | Result | Evidence |
|---------|--------|----------|
| CODE-ASSUME-01 | PASS | Tests reference `rfo.select_stuck`, `rfo.main`, and the `SYNTH_CACHE`/`OUTCOMES_LOG`/`RUNS_DIR`/`CLAUDE_BIN` module-level globals. All confirmed present in the implementation (see `grep -nE "^(def|class) " refine_from_outcomes.py`). |
| CODE-ASSUME-02 | PASS | Only stdlib + `gold_added_lines` from `memory.to_memory_entry` (verified import works). |
| CODE-EDIT-01 | PASS | One Write per file; subsequent verifications used Bash, not Edit on the same file. |
| CODE-LINT-01 | PASS | `uv run ruff check` clean on test file. |
| CODE-TEST-01 | PASS | All fixtures use `tmp_path`; `subprocess.run` monkeypatched; real `_oracle/outcomes_log.json` + `_oracle/synth_cache.json` paths overridden via `monkeypatch.setattr(rfo, "SYNTH_CACHE", ...)`. Only `gold_added_lines("sympy__sympy-15976")` reads the read-only gold.patch fixture under `_oracle/sympy__sympy-15976/` for the leak-scrub scenario, which is permitted and necessary to exercise scrub_leak. |
| CODE-TEST-03 | PASS | Red state captured `ImportError: cannot import name 'refine_from_outcomes' from 'memory'` — the structural failure shape mandated by the sprint contract. |
| CODE-VERIFY-01 | PASS | After 006, test file is 10/10 PASS AND scoped harness regression stays 26/26. |
| CODE-VERIFY-02 | PASS | `arm_context._synth_entry` change re-verified via the full `harness/tests/` + `memory/tests/` sweep. |
| CODE-SCOPE-01 | PASS | Only `experiments/agentbook-ab/memory/tests/__init__.py` and `experiments/agentbook-ab/memory/tests/test_refine_from_outcomes.py` created. No other file touched by Task 005. |
| CODE-SCOPE-02 | N/A | No commit was produced this batch yet (commit happens at sprint exit). |

### Task 006 (impl, Green)

| Item ID | Result | Evidence |
|---------|--------|----------|
| CODE-ASSUME-01 | PASS | All referenced helpers (`_extract_json`, `_synth_env`, `gold_added_lines`, `scrub_leak`) verified existing in their source modules before import. |
| CODE-ASSUME-02 | PASS | Re-uses `_extract_json` and `_synth_env` from `memory.synthesize` (no rename). `EXP_ROOT` and `ORACLE` confirmed exported from `benchmark.paths`. |
| CODE-EDIT-01 | PASS | The arm_context.py modification used Read-then-Edit; PostToolUse hooks did not reformat that edit region. |
| CODE-LINT-01 | PASS | `uv run ruff check --fix experiments/agentbook-ab/memory/refine_from_outcomes.py experiments/agentbook-ab/pipeline/arm_context.py` returns `All checks passed!`. |
| CODE-TEST-01 | PASS | Implementation imports `subprocess` only inside `call_opus`; tests monkeypatch it; no real Opus traffic in either Red or Green runs. |
| CODE-TEST-03 | N/A | Impl task, not test task. |
| CODE-VERIFY-01 | PASS | Both test commands from task-006 Verification Commands exit 0. |
| CODE-VERIFY-02 | PASS | Shared-infra change to `_synth_entry` re-validated by full scoped sweep (36/36). |
| CODE-SCOPE-01 | PASS | Only `experiments/agentbook-ab/memory/refine_from_outcomes.py` (new) and `experiments/agentbook-ab/pipeline/arm_context.py` (`_synth_entry` only) touched. No `memory/_claude_io.py` refactor was needed — re-using `_extract_json` and `_synth_env` by import from `memory.synthesize` kept synthesize.py untouched. |
| CODE-SCOPE-02 | N/A | No commit produced this batch yet. |

## Sprint Contract Acceptance Criteria

### Task 005 acceptance

- [x] `experiments/agentbook-ab/memory/tests/__init__.py` exists (empty).
- [x] `experiments/agentbook-ab/memory/tests/test_refine_from_outcomes.py` exists with exactly 10 test functions, one per Feature 1 scenario, named per task-005 Step 3.
- [x] All 10 tests FAIL Red with the structural failure (`ImportError: cannot import name 'refine_from_outcomes'`).
- [x] Each test docstring quotes/names its source scenario.
- [x] Per-test wall-time budget < 50 ms; full file wall-time 0.11s well under 0.5s.
- [x] No new external Python dependencies.
- [x] No other test file regresses (harness 26/26 stays green).
- [x] Red-state confirmation matches sprint contract: collection error naming the missing module.

### Task 006 acceptance

- [x] Full CLI present with all 14 flags.
- [x] `select_stuck` returns deterministic `(-fails, iid)` sort, restricted to `RUNTIME_ARMS`.
- [x] `harvest_failing_transcripts` filters `**/tests/**` / `test_*.py` paths AND `gold_added_lines(iid)` lines AND truncates observations to 200 chars.
- [x] `build_refine_prompt` validates pre-return against gold and test paths (`ValueError` on violation, including the verbatim hard-rule allowance for the literal "no test file paths" rule line).
- [x] `call_opus` mirrors synthesize.py mechanics (claude -p, --no-session-persistence, disallowedTools, isolated temp cwd, `_synth_env()`).
- [x] `write_revision` holds `threading.Lock`, lazy-inits revisions[0], validates non-empty root_cause_pattern → `ValueError("empty_root_cause_pattern")`, runs `scrub_leak`, appends full-lineage revision, mirrors aliases (gated by `mirror_aliases` parameter that the regression check toggles).
- [x] `_extract_json` re-used from `memory.synthesize` (import; no duplication, no refactor).
- [x] `_synth_entry` updated with revisions-aware merged-view branch; backwards-compat for entries without `revisions`.
- [x] `--dry-run` prints planned tasks + would-be prompt; traced as 0 subprocess.run calls.
- [x] `--help` lists every documented flag.
- [x] `--rollback-to-rev N` flag implemented (`rollback_to_rev` function; records in `entry["rollback_history"]`).
- [x] All 10 tests in `memory/tests/test_refine_from_outcomes.py` PASS.
- [x] `harness/tests/` + `memory/tests/` 36/36 stay green.
- [x] Ruff clean.
- [x] No new external Python dependencies.
- [x] Anti-stub: no `TODO`/`FIXME`/`NotImplementedError`/`pass`-only function bodies (verified by grep).

## Rework Items

(None.)

## Pivot

`pivot_required: false`

## Recurring Patterns

None detected across the batch.

## Verdict

**PASS**

Both tasks meet the sprint-contract acceptance criteria. All checklist items applicable to this batch pass. 10 new refinement tests Green; 26 harness tests still Green; ruff clean; CLI surfaces all documented flags; dry-run mode confirmed zero subprocess calls.
