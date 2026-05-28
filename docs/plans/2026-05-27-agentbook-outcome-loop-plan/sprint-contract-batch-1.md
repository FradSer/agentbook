# Batch 1 Sprint Contract

## Tasks

| ID  | Subject | Type |
|-----|---------|------|
| 001 | Pre-flight token-cap baseline | setup/ops |
| 002 | Lenient Edit Parser tests (Features 2+3) | test |
| 003 | Lenient Edit Parser implementation (Features 2+3) | impl |
| 004 | Batch 1 exit gate (full 17-task gemma4_e4b sweep) | ops |

## Acceptance Criteria

Acceptance criteria are auto-derived from each task file's BDD Scenario Then-clauses and Success Criteria.

### Task 001: Pre-flight token-cap baseline

- [ ] `experiments/agentbook-ab/harness/llm_ollama.py:54` set to either `max_tokens=16000` (Branch A) or `max_tokens=8000` (Branch B/C); choice recorded in SUMMARY.md
- [ ] `experiments/agentbook-ab/runs_v2.preflight/SUMMARY.md` exists with: `truncated_no_block_notes_pre/post`, `15976_resolved_post`, `mean_turns_used_pre/post`, chosen branch letter (A/B/C), Batch-1 gate-5 threshold (`K_post ≥ K_pre` or `K_post == K_pre`)
- [ ] `runs_v2.preflight/` is read-only (archived); a fresh empty `runs_v2/` is staged for Batch 1
- [ ] SUMMARY.md cites the corresponding [batching-strategy.md](./2026-05-27-agentbook-outcome-loop-design/batching-strategy.md) branch
- [ ] **[AUTO-RESOLVED]** Wall-clock cost: gemma4:e4b runs 12 cells (4 arms × 3 samples) on `sympy__sympy-15976` with `--workers 1`; expected ~30-60 min. The orchestrator command may be launched via `Bash(run_in_background=True)` so the sub-agent does not block synchronously; poll periodically until `runs_v2/` contains all 12 expected cell directories or `consume_idx` confirms completion via `_oracle/outcomes_log.json` refresh

### Task 002: Lenient Edit Parser tests (Features 2+3)

- [ ] Exactly 11 new test functions added to `experiments/agentbook-ab/harness/tests/test_search_replace.py`
- [ ] Every new test FAILS (Red) — failure shape is structural (`AttributeError`/`ImportError` for missing helpers, or empty-list returns from `extract_edits` where a tuple is expected)
- [ ] All 15 existing tests still pass
- [ ] Total file wall time under pytest stays ≤ 0.5s (per-test < 50 ms target)
- [ ] Each new test's docstring (or test name) quotes the scenario's `Then` clauses so the link to bdd-specs.md is direct
- [ ] No new external Python imports (stdlib + project's own modules only)
- [ ] **Red-state confirmation (PLAN-VERIFY-02 / CODE-TEST-03):** running `uv run python -m pytest experiments/agentbook-ab/harness/tests/test_search_replace.py -q` produces 11 failures whose error messages name the missing symbol or expected tuple (NOT collection errors from unrelated imports)

### Task 003: Lenient Edit Parser implementation (Features 2+3)

- [ ] All 26 tests in `harness/tests/test_search_replace.py` PASS (15 existing + 11 new from task-002)
- [ ] `harness/prompts.py` exports `looks_like_edit_intent` and `diagnose_edit_block`; `extract_edits` keeps its existing signature; no other public symbol changes
- [ ] `harness/agent_loop.py` carries the new `_EDIT_MALFORMED_HINT` constant and the malformed-edit branch; `consecutive_parse_failures` still increments under the new branch; 6-strike abort still fires
- [ ] Ruff passes on both modified files
- [ ] No new external Python dependencies
- [ ] `extract_edits` is still O(text) on well-formed input (fast path unchanged); fallback enters only when `_INTENT_RE.search` matches and fast path returned []
- [ ] **Anti-stub (CODE-QUAL-01/02):** no `TODO`/`FIXME`/`NotImplementedError`/`pass`-only function bodies in the diff

### Task 004: Batch 1 exit gate (full 17-task gemma4_e4b sweep)

- [ ] `runs_v2.batch1/SUMMARY.md` exists with all 5 gate rows (Unit tests; truncated-no-block notes ≤ 0.2 × pre; doom-loop episodes == 0; no regression; union holds or grows per the gate-5 threshold task-001 picked) resolved against the thresholds (`PASS`/`FAIL`)
- [ ] The branch decision ("Advance to Batch 2" or "Stop") is the last line of the summary and cites a specific failing gate when blocked
- [ ] `_oracle/outcomes_log.json` is refreshed and pinned to the Batch 1 baseline
- [ ] Gate 4 — `regression_count == 0`: every task resolved pre-Batch-1 still resolves
- [ ] If `select_stuck(model_slug="gemma4_e4b", min_failure_count=3)` against the new outcomes log returns empty AND gates 1-4 pass, the summary explicitly notes "Batch 2 deferred — nothing to refine"
- [ ] **[AUTO-RESOLVED]** Wall-clock cost: ~204 cells (17 tasks × 4 arms × 3 samples) on gemma4:e4b. Expected several hours. The orchestrator command runs via `Bash(run_in_background=True)`; the sub-agent polls until the expected cell count is reached or escalates with `REWORK_ESCALATED` after a bounded watch window so the main agent can take over polling across turns

## Red-Green Pairs

| Test Task | Impl Task | Expected Red State | Expected Green State |
|-----------|-----------|--------------------|----------------------|
| 002 | 003 | `uv run python -m pytest experiments/agentbook-ab/harness/tests/test_search_replace.py -q` shows 11 new tests fail with `AttributeError`/`ImportError`/empty-list mismatches naming the missing helpers (NOT collection errors); existing 15 tests pass | Same pytest invocation returns 26/26 PASS |

Tasks 001 and 004 are not Red-Green pairs — they are operator-style measurement tasks. The acceptance contract for them is the SUMMARY.md presence + the threshold computations being correct on the archived outcomes_log.

## Evaluation Criteria Preview

The evaluator will apply the following checklist items from `docs/retros/checklists/code-v1.md` to this batch:

| Item ID | Description |
|---------|-------------|
| CODE-ASSUME-01 | Before writing a test referencing a fixture/helper/repository method/attribute by name, grep for its existence in the target module or conftest |
| CODE-ASSUME-02 | Before importing a type from a shared module, confirm the exact exported name |
| CODE-EDIT-01 | If a PostToolUse hook reformats a file after a Write, Read before the next Edit on that file |
| CODE-EDIT-02 | When a formatter auto-removes an import, re-add it adjacent to other imports in the same module |
| CODE-LINT-01 | Every task concludes with a lint run (`uv run ruff check`) before marking completed |
| CODE-TEST-01 | Unit tests must not hit a real database, network, or third-party API; use in-memory repos / fake providers / clock fixtures |
| CODE-TEST-02 | Integration tests requiring Docker/Postgres are gated behind `RUN_DOCKER_TESTS=1` or equivalent env check |
| CODE-TEST-03 | Red tests assert the failure mode the feature would produce, not an incidental collection error |
| CODE-VERIFY-01 | Before marking a task completed, the test command from the task file exits 0 AND the full-suite regression command also exits 0 |
| CODE-VERIFY-02 | Intermediate refactors that touch shared infrastructure re-run the entire unit suite |
| CODE-SCOPE-01 | A task changes only the files listed in its "Files to Modify/Create" section (with limited natural-import exceptions) |
| CODE-SCOPE-02 | A task's commit message names the feature scope, not individual file moves |

CODE-MIGRATION-01/02 do not apply to this batch (no Alembic migrations).

## Sign-off

- **Generator:** executing-plans
- **Timestamp:** 2026-05-29T00:00:00Z
- **Status:** READY
- **Revision:** 0
