# Task 005: refine_from_outcomes tests (Feature 1)

**depends-on**: task-004

## Description

Add the full Red-phase test suite for `memory/refine_from_outcomes.py`. Create `experiments/agentbook-ab/memory/tests/__init__.py` and `experiments/agentbook-ab/memory/tests/test_refine_from_outcomes.py` with 10 tests covering all Feature 1 scenarios. Tests monkeypatch `subprocess.run` (Opus stub returns canned JSON), construct synthetic `_oracle/outcomes_log.json` + minimal `runs_v2/<iid>__<arm>__<model_slug>__s*/result.json` + `transcript.json` fixtures under `tmp_path`, and assert the per-task isolation, idempotency, gold-leak scrub, and lineage invariants. All new tests MUST fail Red.

Use stdlib only. The `gold_added_lines` and `scrub_leak` imports from `memory/to_memory_entry.py` are real (no monkeypatching needed); the Opus stub replaces the `subprocess.run` call site that task-006 will introduce.

## Execution Context

**Task Number**: 005 of 016
**Phase**: Batch 2 — Outcome-Driven Cue Refinement (RED)
**Prerequisites**:
- task-004 complete: Batch 1 exit gate PASSED and Batch 2 entry-gate condition `select_stuck(min_failure_count=3) ≥ 1 iid` holds.
- `K_pre` recorded in `runs_v2.batch1/SUMMARY.md` for the recovery-rate denominator.

## BDD Scenario

```gherkin
Feature: refine_from_outcomes appends a new cue revision for stuck tasks

Background:
  Given _oracle/synth_cache.json carries a revision-0 entry for "sympy__sympy-15976"
  And _oracle/outcomes_log.json contains gemma4_e4b s0..s2 across 5 arms on sympy__sympy-15976 with resolved=false
  And runs_v2/sympy__sympy-15976__*gemma4_e4b__s*/transcript.json files exist for those failing runs
  And min_failure_count is 3

Scenario: Happy path -- one stuck task refined and versioned
  Given gold_added_lines("sympy__sympy-15976") returns a non-empty set
  And refine_from_outcomes is invoked with --only sympy__sympy-15976 --workers 1
  When the script runs
  Then a subprocess.run call is made to claude -p with the refinement prompt
  And the prompt body includes the existing root_cause_pattern, localization_cues, verification_method
  And the prompt body includes a digest of failing-turn observations and parse-failure notes
  And the prompt body does NOT include any line from gold_added_lines("sympy__sympy-15976")
  And the prompt body does NOT include any path under tests/ or matching test_*.py
  And the refined JSON is parsed, normalized, and scrubbed
  And synth_cache["sympy__sympy-15976"]["revisions"][0] equals the prior entry's knowledge fields with rev=0
  And synth_cache["sympy__sympy-15976"]["revisions"][1] is the new refined entry with rev=1, parent_revision=0
  And synth_cache["sympy__sympy-15976"]["revisions"][1]["refined_from"] lists the harvested run identifiers
  And synth_cache["sympy__sympy-15976"]["revisions"][1]["change_rationale"] is a non-empty string
  And synth_cache["sympy__sympy-15976"]["root_cause_pattern"] equals revisions[-1].root_cause_pattern
  And synth_cache["sympy__sympy-15976"]["localization_cues"] equals revisions[-1].localization_cues
  And synth_cache["sympy__sympy-15976"]["verification_method"] equals revisions[-1].verification_method

Scenario: Under-evidenced stuck task is skipped with reason logged
  Given runs_v2 contains only 1 failing transcript for "sympy__sympy-16450"
  And min_failure_count is 3
  When refine_from_outcomes runs over sympy__sympy-16450
  Then no Opus subprocess call is made for sympy__sympy-16450
  And the log records "skip sympy__sympy-16450: under-evidenced (1<3)"
  And synth_cache["sympy__sympy-16450"] is byte-for-byte unchanged

Scenario: Gold-leaked content in refinement output is scrubbed
  Given gold_added_lines("sympy__sympy-15976") includes "return Integer(1)"
  And Opus returns refined cues containing the verbatim line "return Integer(1)"
  When refine_from_outcomes processes the entry
  Then scrub_leak rewrites the verbatim line to "…"
  And revisions[-1]["leak_lines_removed"] is at least 1
  And no revision field contains the verbatim gold line

Scenario: Malformed JSON from Opus leaves prior revisions untouched
  Given Opus returns a string with neither a ```json fenced block nor a parsable {...} substring
  When refine_from_outcomes processes "sympy__sympy-16766"
  Then a single ERROR line is logged including the iid and exception class
  And synth_cache["sympy__sympy-16766"]["revisions"] has the same length as before
  And other tasks in the same batch still succeed (per-task isolation)

Scenario: Refinement that empties root_cause_pattern is rejected before write
  Given Opus returns refined fields with root_cause_pattern="" (empty after strip)
  When refine_from_outcomes validates the refined entry
  Then ValueError is raised inside the per-task worker
  And the entry is left at its prior revisions length
  And the rejection is logged with iid and reason="empty_root_cause_pattern"

Scenario: Empty outcomes log is a no-op
  Given _oracle/outcomes_log.json is "[]"
  When refine_from_outcomes runs with no --only filter
  Then no tasks are selected
  And the log prints "refining 0/0 stuck tasks"
  And synth_cache.json is byte-for-byte unchanged

Scenario: Re-running refinement is idempotent without --redo
  Given refine_from_outcomes already produced revision 1 for "sympy__sympy-15976"
  When refine_from_outcomes is invoked a second time without --redo
  Then no Opus subprocess call is issued for "sympy__sympy-15976"
  And the log records "skip sympy__sympy-15976: already refined (revisions=2)"
  And synth_cache["sympy__sympy-15976"]["revisions"] is unchanged

Scenario: --redo forces a new revision even if one exists
  Given refine_from_outcomes already produced revision 1 for "sympy__sympy-15976"
  When refine_from_outcomes is invoked with --redo --only sympy__sympy-15976
  Then Opus is called once
  And synth_cache["sympy__sympy-15976"]["revisions"] has length 3
  And revisions[2]["parent_revision"] equals 1

Scenario: One task's failure does not poison sibling tasks
  Given two stuck tasks "sympy__sympy-15976" and "sympy__sympy-16766" are eligible
  And the Opus subprocess for "sympy__sympy-16766" raises subprocess.TimeoutExpired
  When refine_from_outcomes runs with --workers 2
  Then "sympy__sympy-15976" advances to revision 1
  And "sympy__sympy-16766" stays at its prior revision count
  And the failure line names "sympy__sympy-16766" and the exception class

Scenario: Stuck-task selection prefers full-failure tasks deterministically
  Given gemma4_e4b has 0/3 resolved on every arm for sympy__sympy-15976 (15 failures)
  And gemma4_e4b has 2/3 resolved for sympy__sympy-15875 on good_loop (4 failures)
  When refine_from_outcomes selects candidates with require_zero_wins=True, min_failure_count=3
  Then sympy__sympy-15976 is selected
  And sympy__sympy-15875 is NOT selected
  And selection order on ties is alphabetical
```

**Spec Source**: [bdd-specs.md Feature 1](../2026-05-27-agentbook-outcome-loop-design/bdd-specs.md)

## Files to Modify/Create

- Create: `experiments/agentbook-ab/memory/tests/__init__.py` (empty file, marks the directory as a test package).
- Create: `experiments/agentbook-ab/memory/tests/test_refine_from_outcomes.py` — 10 tests, one per Feature 1 scenario.

## Steps

### Step 1: Verify scenarios are present in the design
- Confirm bdd-specs.md Feature 1 carries the 10 scenarios above verbatim. Use the scenario name in the test function name (`test_happy_path_one_stuck_task_refined`, `test_under_evidenced_stuck_task_skipped`, ...).

### Step 2: Build fixture helpers
- Add `_write_fixture(tmp_path, ...)` helpers that materialize a minimal `_oracle/synth_cache.json`, `_oracle/outcomes_log.json`, and `runs_v2/<iid>__<arm>__<model_slug>__s*/{result.json,transcript.json}` tree.
- Add an `_opus_stub` helper returning a `subprocess.CompletedProcess`-shape stub whose `stdout` is the canned refined-JSON `claude -p --output-format json` envelope.

### Step 3: Add the 10 tests (Red)
- **`test_happy_path_one_stuck_task_refined`**: full happy-path assertions — `subprocess.run` called once with prompt containing required fields and excluding all `gold_added_lines("sympy__sympy-15976")` lines and all `tests/`/`test_*.py` paths; resulting `synth_cache["sympy__sympy-15976"]["revisions"]` has length 2 with the lineage fields populated; top-level aliases mirror `revisions[-1]`.
- **`test_under_evidenced_stuck_task_skipped`**: only 1 failing transcript present → no Opus call → log carries "skip ... under-evidenced (1<3)" → cache unchanged byte-for-byte.
- **`test_gold_leak_in_refinement_output_scrubbed`**: Opus stub returns refined cues containing a `gold_added_lines` line; assert `scrub_leak` rewrites it; assert `revisions[-1]["leak_lines_removed"] >= 1`.
- **`test_malformed_opus_json_leaves_prior_untouched`**: Opus stub returns "not JSON at all"; assert ERROR log line includes iid + exception class; assert revisions length unchanged.
- **`test_refinement_with_empty_root_cause_rejected`**: Opus stub returns refined fields with `root_cause_pattern=""`; assert `ValueError` raised inside the worker; assert revisions length unchanged; assert rejection log includes `iid` and `reason="empty_root_cause_pattern"`.
- **`test_empty_outcomes_log_is_noop`**: empty `_oracle/outcomes_log.json`; assert log says "refining 0/0 stuck tasks"; assert `synth_cache.json` bytes unchanged.
- **`test_idempotent_without_redo`**: pre-seed revisions=2; run again without `--redo`; assert no Opus call; assert log carries "skip ... already refined (revisions=2)".
- **`test_redo_forces_new_revision`**: pre-seed revisions=2; run with `--redo --only sympy__sympy-15976`; assert one Opus call; assert revisions length=3; assert `revisions[2]["parent_revision"] == 1`.
- **`test_one_task_failure_does_not_poison_siblings`**: Opus stub raises `subprocess.TimeoutExpired` for 16766 but returns happy JSON for 15976; `--workers 2`; assert 15976 advances; assert 16766 unchanged; assert error log names 16766 + exception class.
- **`test_stuck_task_selection_prefers_zero_wins`**: feed an outcomes log with 0/15 for 15976 and 2/3 (wins>0) for 15875; assert `select_stuck(require_zero_wins=True, min_failure_count=3)` returns `["sympy__sympy-15976"]` only; tie-break alphabetical.

### Step 4: Confirm Red status
- The whole file fails (collection error for the missing `memory.refine_from_outcomes` import is acceptable — task-006 supplies the module).

## Verification Commands

```bash
# Run only the new tests — expect collection error or all fail (Red)
cd experiments/agentbook-ab && \
  uv run python -m pytest memory/tests/test_refine_from_outcomes.py -q

# Wall-time budget check on the test file
cd experiments/agentbook-ab && time uv run python -m pytest memory/tests/test_refine_from_outcomes.py -q

# Confirm the rest of the suite is still green
cd experiments/agentbook-ab && \
  uv run python -m pytest --ignore=memory/tests -q
```

## Success Criteria

- Exactly 10 new test functions in `memory/tests/test_refine_from_outcomes.py`, one per Feature 1 scenario.
- `memory/tests/__init__.py` exists (empty).
- All 10 tests FAIL (Red) — failure shape is either `ImportError: No module named memory.refine_from_outcomes` at collection time or `AttributeError` for missing symbols.
- No new external Python dependencies.
- Per-test wall-time budget < 50 ms (stdlib monkeypatching only).
- No other test file regresses.
- Each test docstring references the scenario name from bdd-specs.md for traceability.
