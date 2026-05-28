# Task 002: Lenient Edit Parser tests (Features 2 + 3)

**depends-on**: task-001

## Description

Add the full Red-phase test suite for the Lenient Edit Parser and its paired malformed-edit feedback hint. Extend `experiments/agentbook-ab/harness/tests/test_search_replace.py` with tests covering all 10 Feature 2 scenarios (lenient `extract_edits` recovery paths) and all 5 Feature 3 scenarios (`looks_like_edit_intent`, `diagnose_edit_block`, `agent_loop` dispatch branch). All new tests MUST fail (Red) before task-003 implementation lands; all 15 existing tests in the file MUST continue to pass.

Use stdlib + `tmp_path` only. The `agent_loop` dispatch-branch test (Feature 3 scenario 5) uses an in-memory LLM stub conforming to the existing `harness.llm_ollama.OllamaLLM` shape (returns canned replies per turn) and a tiny scripted `messages` list — no real Ollama, no real `subprocess.run`.

## Execution Context

**Task Number**: 002 of 016
**Phase**: Batch 1 — Lenient Edit Parser (RED)
**Prerequisites**:
- task-001 complete: pre-flight branch chosen; `harness/llm_ollama.py:54` in its branch-specified terminal state.
- Existing `harness/tests/test_search_replace.py` runs green under `uv run python -m pytest experiments/agentbook-ab/harness/tests/ -q`.

## BDD Scenario

```gherkin
Feature: extract_edits recovers truncated or off-fence SEARCH/REPLACE blocks

Background:
  Given the strict _EDIT_RE / _SR_RE patterns remain the fast path
  And every test currently in harness/tests/test_search_replace.py is in the suite

Scenario: Closing fence missing because the model hit max_tokens
  Given an assistant message opening with "```edit\npath/x.py\n<<<<<<< SEARCH\na = 1\n=======\na = 2\n>>>>>>> REPLACE\n"
  And the message has no closing triple-backtick
  When extract_edits parses the message
  Then it returns exactly one tuple
  And the path equals "path/x.py"
  And the search equals "a = 1"
  And the replace equals "a = 2"

Scenario: Fence tagged ```python instead of ```edit is still parsed
  Given an assistant message with a fenced ```python block containing a valid SEARCH/REPLACE pair
  When extract_edits parses the message
  Then it returns exactly one tuple
  And the path comes from the first non-empty pre-SEARCH line inside the block

Scenario: Raw SEARCH/REPLACE markers with no opening fence are recovered when a path precedes them
  Given an assistant message "Here is the fix.\n\npath/x.py\n<<<<<<< SEARCH\nx = 1\n=======\nx = 2\n>>>>>>> REPLACE\n"
  When extract_edits parses the message
  Then it returns exactly one tuple ("path/x.py", "x = 1", "x = 2")

Scenario: Reply with neither SR markers nor ```edit returns empty list
  Given an assistant message "Let me think. I will grep next.\n\n```bash\nls\n```\n"
  When extract_edits parses the message
  Then it returns []
  And the lenient fallback is NOT entered (no _INTENT_RE match)

Scenario: Carets-and-equals whitespace tolerance
  Given an assistant message with "<<<<< SEARCH", trailing spaces on the ======= line, and ">>>>>>>> REPLACE" (mixed caret counts)
  When extract_edits parses the message
  Then it returns exactly one tuple
  And the search and replace bodies are stripped of leading/trailing whitespace correctly

Scenario: Path-on-fence-line ("```edit path/x.py")
  Given an assistant message "```edit path/x.py\n<<<<<<< SEARCH\nold\n=======\nnew\n>>>>>>> REPLACE\n```"
  When extract_edits parses the message
  Then it returns exactly one tuple ("path/x.py", "old", "new")

Scenario: Two complete SEARCH/REPLACE pairs in one unfenced block both recover
  Given an unclosed ```edit block under one path with two complete SEARCH/REPLACE pairs
  When extract_edits parses the message
  Then it returns 2 tuples sharing the same path

Scenario: Truncated final pair is dropped, prior complete pairs kept
  Given an unclosed ```edit block with one complete SEARCH/REPLACE pair followed by "<<<<<<< SEARCH\na = 1\n=====<truncated>"
  When extract_edits parses the message
  Then it returns exactly 1 tuple (the complete pair)
  And the incomplete pair is silently discarded

Scenario: End-to-end -- truncated edit block parses AND applies to a real file
  Given a tmp_path repo containing mod.py with "def f():\n    return 0\n"
  And an assistant message that opens a ```edit block targeting mod.py with SEARCH "return 0" / REPLACE "return 1" but no closing fence
  When extract_edits then apply_search_replace runs
  Then mod.py is rewritten to "def f():\n    return 1\n"

Scenario: Test-file edit refusal still fires for a recovered (unfenced) block
  Given the lenient fallback recovers a tuple ("tests/test_x.py", "old", "new")
  When apply_search_replace receives that tuple
  Then it returns (False, msg) where msg contains "test file"
  And the working tree is unchanged
```

```gherkin
Feature: agent_loop breaks the doom-loop on unparseable edit intent

Scenario: looks_like_edit_intent detects partial markers
  Given the assistant message "```edit\n...\n"
  When looks_like_edit_intent is called
  Then it returns true
  Given the assistant message "<<<<<<< SEARCH\nfoo\n"
  Then looks_like_edit_intent returns true
  Given the assistant message "just bash\n```bash\nls\n```\n"
  Then looks_like_edit_intent returns false

Scenario: diagnose_edit_block classifies the missing closing fence
  Given the assistant message "```edit\nmod.py\n<<<<<<< SEARCH\nold\n=======\nnew\n>>>>>>> REPLACE\n" (no closing fence)
  When diagnose_edit_block is called
  Then the returned string contains "closing triple-backtick"

Scenario: diagnose_edit_block classifies missing separator
  Given the assistant message "```edit\nmod.py\n<<<<<<< SEARCH\nold\n>>>>>>> REPLACE\n```\n"
  When diagnose_edit_block is called
  Then the returned string contains "=======" or "separator"

Scenario: diagnose_edit_block classifies truncated mid-block
  Given the assistant message "```edit\nmod.py\n<<<<<<< SEARCH\nold\n=======\nnew\n"
  When diagnose_edit_block is called
  Then the returned string contains "REPLACE"

Scenario: agent_loop emits _EDIT_MALFORMED_HINT instead of _NO_BLOCK_HINT
  Given an episode in progress where the model emits a truncated ```edit block
  And extract_edits returns []
  And looks_like_edit_intent(reply) returns true
  When agent_loop processes the turn
  Then the next user message contains the malformed-block diagnosis
  And the next user message does NOT contain "Respond with EXACTLY ONE ```bash"
  And consecutive_parse_failures increments by 1
  And the episode does NOT abort yet (assuming this is below the 6-strike cap)
```

**Spec Source**: [bdd-specs.md Feature 2 + Feature 3](../2026-05-27-agentbook-outcome-loop-design/bdd-specs.md)

## Files to Modify/Create

- Modify: `experiments/agentbook-ab/harness/tests/test_search_replace.py` — append 11 new `test_*` functions (Feature 2 consolidates 10 scenarios into 8 functions per architecture.md "11 new tests"; Feature 3 contributes the remaining 3). Existing 15 tests stay byte-for-byte unchanged.

## Steps

### Step 1: Verify the scenarios are present in the design
- Confirm bdd-specs.md Features 2 and 3 carry the 15 scenarios above verbatim. Quote each scenario's `Then` clauses in the test docstring so future readers see the contract.

### Step 2: Add Feature 2 tests (Red)
- Add `test_lenient_closing_fence_missing`, `test_lenient_python_fence`, `test_lenient_raw_markers_with_preceding_path`, `test_lenient_no_intent_returns_empty`, `test_lenient_whitespace_tolerance`, `test_lenient_path_on_fence_line`, `test_lenient_two_complete_pairs_unfenced`, `test_lenient_truncated_final_pair_dropped`, `test_lenient_truncated_recovers_and_applies` (end-to-end against `tmp_path`), `test_lenient_test_file_refusal_holds`.
- Each test calls `extract_edits(msg)` (and for the e2e test, then `apply_search_replace`) and asserts the exact tuple list specified in the scenario.
- **Verification**: `uv run python -m pytest experiments/agentbook-ab/harness/tests/test_search_replace.py -q` shows the new tests FAIL (because the lenient regexes / fallback do not yet exist) while the existing 15 tests still pass.

### Step 3: Add Feature 3 tests (Red)
- Add `test_looks_like_edit_intent_partial_markers` (asserts true/true/false against the three scenario inputs).
- Add `test_diagnose_edit_block_classifies` (single parameterized test or three small tests asserting the substring requirements: `"closing triple-backtick"`, `"=======" or "separator"`, `"REPLACE"`).
- Add `test_agent_loop_emits_edit_malformed_hint`: spin up an episode with a stubbed `OllamaLLM` whose `chat()` returns a single truncated ```edit reply on turn 0 then a no-op on turn 1. Patch the `agent_loop` `messages` accumulator and assert: the appended user-role message contains the diagnosis substring, does NOT contain `"Respond with EXACTLY ONE ```bash"`, `consecutive_parse_failures` reached 1, and `episode.stop_reason` is NOT `"parse_failures"`.
- **Verification**: same pytest invocation — the 3 new tests FAIL (helpers/branch not yet implemented).

### Step 4: Confirm Red status holistically
- Run the full file. Count failing tests = 11. Existing 15 tests still pass. Total = 26 collected.

## Verification Commands

```bash
# Run only the new tests, expecting FAILURES (Red phase)
cd experiments/agentbook-ab && \
  uv run python -m pytest harness/tests/test_search_replace.py -q

# Confirm existing tests still pass in isolation
cd experiments/agentbook-ab && \
  uv run python -m pytest harness/tests/test_search_replace.py -q -k "not lenient and not diagnose and not malformed and not edit_intent"

# Wall-time budget check (< 2s total per best-practices.md)
cd experiments/agentbook-ab && time uv run python -m pytest harness/tests/test_search_replace.py -q
```

## Success Criteria

- Exactly 11 new test functions added to `harness/tests/test_search_replace.py`.
- Every new test FAILS (Red) — failure is structural (`AttributeError`/`ImportError` for missing `looks_like_edit_intent` / `diagnose_edit_block`, or empty-list returns from `extract_edits` where a tuple is expected).
- All 15 existing tests still pass.
- Total file wall time under pytest stays ≤ 0.5s (per-test < 50 ms target).
- Each new test's docstring (or test name) quotes the scenario's `Then` clauses so the link to bdd-specs.md is direct.
- No new external Python imports (stdlib + project's own modules only).
