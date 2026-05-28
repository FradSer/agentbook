# Batch 2 Sprint Contract

## Tasks

| ID  | Subject | Type |
|-----|---------|------|
| 005 | refine_from_outcomes tests (Feature 1) | test |
| 006 | refine_from_outcomes implementation + _synth_entry revision-aware reader | impl |

Task **007** (Batch 2 exit gate; refined-iid re-eval + regression sweep) is operator-deferred per the user's wall-time pivot decision recorded in `handoff-summary-1.md`. Its command stays documented for the operator; this batch ships only the code.

## Acceptance Criteria

### Task 005: refine_from_outcomes tests (Feature 1)

- [ ] `experiments/agentbook-ab/memory/tests/__init__.py` exists (empty file).
- [ ] `experiments/agentbook-ab/memory/tests/test_refine_from_outcomes.py` exists with exactly **10 test functions**, one per Feature 1 scenario, named after each scenario (e.g. `test_happy_path_one_stuck_task_refined`).
- [ ] All 10 tests FAIL Red — either `ImportError: No module named memory.refine_from_outcomes` at collection time or `AttributeError` for missing symbols. Failures must be structural (the right reason per CODE-TEST-03), not incidental fixture errors.
- [ ] Each test docstring quotes (or names) its source scenario from `bdd-specs.md` Feature 1 for traceability.
- [ ] Per-test wall-time budget < 50 ms; full file wall-time < 0.5s.
- [ ] No new external Python dependencies; stdlib + project modules only.
- [ ] No other test file regresses (`uv run python -m pytest experiments/agentbook-ab/harness/tests/ -q` stays 26/26).
- [ ] **Red-state confirmation (PLAN-VERIFY-02 / CODE-TEST-03):** `uv run python -m pytest experiments/agentbook-ab/memory/tests/test_refine_from_outcomes.py -q` reports collection error OR 10 failures whose error messages name the missing `memory.refine_from_outcomes` module / `select_stuck` / `write_revision` / etc.

### Task 006: refine_from_outcomes implementation + _synth_entry revision-aware reader

- [ ] `experiments/agentbook-ab/memory/refine_from_outcomes.py` exists with full CLI (`--only`, `--model-slug`, `--min-failure-count`, `--redo`, `--workers`, `--model`, `--timeout`, `--dry-run`, `--max-tasks`, `--cues-version`, `--require-no-regression`, `--allow-regression`, `--reason`, `--rollback-to-rev`).
- [ ] Implements `select_stuck(outcomes, model_slug, *, min_failure_count=3, require_zero_wins=True) -> list[str]`. Returns iids meeting the stuck criterion, sorted by `(-fails, iid)` for determinism. Restricted to `arm in RUNTIME_ARMS`.
- [ ] Implements `harvest_failing_transcripts(iid, runs_dir, model_slug, *, arms=RUNTIME_ARMS, max_turns_per_run=4)`. Filters drop any path under `**/tests/**` or matching `test_*.py`. Filters drop any line whose stripped form is in `gold_added_lines(iid)`. Truncates per-turn observations to ≤ 200 chars.
- [ ] Implements `build_refine_prompt(entry, fails)` per architecture.md template. Validates pre-return: no line in prompt body matches any `gold_added_lines(iid)` entry; no `tests/` or `test_*.py` substring.
- [ ] Implements `call_opus(prompt, *, model, timeout)` mirroring `memory/synthesize.py` mechanics (`claude -p`, `--no-session-persistence`, `--disallowedTools WebSearch WebFetch Bash Read Edit Write`, `cwd=tempfile.TemporaryDirectory(prefix="agentbook-refine-")`, `env=_synth_env()`).
- [ ] Implements `write_revision(cache, iid, refined, *, source_tag, cache_path, lock, failure_evidence_count, stuck_criterion, refined_from)` holding a `threading.Lock`. Lazy-init `revisions[0]` from current top-level fields on first write. Validates `refined["root_cause_pattern"].strip()` non-empty → `ValueError("empty_root_cause_pattern")`. Runs `scrub_leak` over refined output; records `leak_lines_removed`. Appends new revision with full lineage fields (`rev`, `parent_revision`, `created_at` ISO UTC, `source`, `model`, `leak_lines_removed`, `failure_evidence_count`, `stuck_criterion`, `refined_from`, `change_rationale`). Mirrors knowledge fields to top-level aliases (gated by `--require-no-regression` when applicable). Persists via `cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n")`.
- [ ] `_extract_json` reused from `memory/synthesize.py` (import or refactor to `memory/_claude_io.py` — pick whichever path keeps synthesize.py's existing tests green).
- [ ] `experiments/agentbook-ab/pipeline/arm_context.py:_synth_entry` updated: when `revisions` is present, return a merged view of `revisions[-1]` knowledge fields over base entry metadata. Backwards-compat preserved — entries without `revisions` return unchanged.
- [ ] `--dry-run` prints the planned tasks and the assembled prompt for one task without any `subprocess.run` call.
- [ ] `--help` lists every documented flag.
- [ ] `--rollback-to-rev N` flag exists and reverts top-level aliases to `revisions[N].<field>` for the given iid.
- [ ] All 10 tests in `memory/tests/test_refine_from_outcomes.py` PASS.
- [ ] Full scoped pytest (`harness/tests/` + `memory/tests/`) stays green.
- [ ] Ruff passes on `memory/refine_from_outcomes.py` and `pipeline/arm_context.py`.
- [ ] No new external Python dependencies.
- [ ] **Anti-stub (CODE-QUAL-01/02):** no `TODO`/`FIXME`/`NotImplementedError`/`pass`-only function bodies in the produced module.

## Red-Green Pairs

| Test Task | Impl Task | Expected Red State | Expected Green State |
|-----------|-----------|--------------------|----------------------|
| 005 | 006 | `uv run python -m pytest experiments/agentbook-ab/memory/tests/test_refine_from_outcomes.py -q` reports collection error OR 10 failures naming the missing module/symbols (NOT incidental fixture errors) | Same pytest invocation returns 10/10 PASS, and `harness/tests/` still 26/26 |

## Evaluation Criteria Preview

The evaluator will apply the following checklist items from `docs/retros/checklists/code-v1.md`:

| Item ID | Description |
|---------|-------------|
| CODE-ASSUME-01 | Before writing a test referencing a fixture/helper/repository method/attribute by name, grep for its existence in the target module or conftest |
| CODE-ASSUME-02 | Before importing a type from a shared module, confirm the exact exported name |
| CODE-EDIT-01 | If a PostToolUse hook reformats a file after a Write, Read before the next Edit on that file |
| CODE-LINT-01 | Every task concludes with a lint run (`uv run ruff check`) before marking completed |
| CODE-TEST-01 | Unit tests must not hit a real database, network, or third-party API; use in-memory repos / fake providers / clock fixtures (anti-leak invariant: the real `_oracle/outcomes_log.json` and `_oracle/synth_cache.json` must not be mutated by tests — use `tmp_path` fixtures) |
| CODE-TEST-03 | Red tests assert the failure mode the feature would produce, not an incidental collection error |
| CODE-VERIFY-01 | Before marking a task completed, the test command from the task file exits 0 AND the scoped regression command also exits 0 |
| CODE-VERIFY-02 | Intermediate refactors that touch shared infrastructure (`memory/synthesize.py`, `pipeline/arm_context.py`) re-run the entire unit suite |
| CODE-SCOPE-01 | A task changes only the files listed in its "Files to Modify/Create" section (with limited natural-import exceptions) |
| CODE-SCOPE-02 | A task's commit message names the feature scope, not individual file moves |

CODE-MIGRATION-01/02 do not apply (no Alembic migrations).

## Sign-off

- **Generator:** executing-plans
- **Timestamp:** 2026-05-29T01:05:00Z
- **Status:** READY
- **Revision:** 0
