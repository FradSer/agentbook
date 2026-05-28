# Task 003: Lenient Edit Parser implementation (Features 2 + 3)

**depends-on**: task-002

## Description

Turn task-002's Red tests Green. Extend `harness/prompts.py` with the lenient regexes (`_INTENT_RE`, `_EDIT_RE_LENIENT`, `_SR_RE_LENIENT`), the helper `_extract_path`, and the new `extract_edits` fallback branch that fires only when the strict fast path returns []. Add `looks_like_edit_intent` and `diagnose_edit_block`. In `harness/agent_loop.py`, insert the third dispatch branch (between `extract_diff` and the `command is None` fallthrough) that fires on `looks_like_edit_intent(text)` when no edit parsed; emit `_EDIT_MALFORMED_HINT` (template constant defined near the top of the file) instead of `_NO_BLOCK_HINT`. Increment `consecutive_parse_failures` so the 6-strike abort still fires; the doom-loop is broken by the *feedback content* changing, not by the cap.

## Execution Context

**Task Number**: 003 of 016
**Phase**: Batch 1 — Lenient Edit Parser (GREEN)
**Prerequisites**:
- task-002 complete: 11 new tests in `harness/tests/test_search_replace.py` failing Red; existing 15 passing.

## BDD Scenario

```gherkin
# This task is the Green pair for task-002. The same 15 scenarios from
# Feature 2 + Feature 3 (quoted verbatim in task-002) are the acceptance
# contract here. The success criterion is the test suite turning fully
# green when this impl lands.

Scenario: Closing fence missing because the model hit max_tokens
  Given an assistant message opening with "```edit\npath/x.py\n<<<<<<< SEARCH\na = 1\n=======\na = 2\n>>>>>>> REPLACE\n"
  And the message has no closing triple-backtick
  When extract_edits parses the message
  Then it returns exactly one tuple ("path/x.py", "a = 1", "a = 2")

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

**Spec Source**: [bdd-specs.md Feature 2 + Feature 3](../2026-05-27-agentbook-outcome-loop-design/bdd-specs.md) (15 scenarios, all quoted in task-002).

## Files to Modify/Create

- Modify: `experiments/agentbook-ab/harness/prompts.py` — add `_INTENT_RE`, `_EDIT_RE_LENIENT`, `_SR_RE_LENIENT`, `_extract_path`, extend `extract_edits` with the fallback branch and the last-resort raw-marker recovery, add `looks_like_edit_intent`, add `diagnose_edit_block`.
- Modify: `experiments/agentbook-ab/harness/agent_loop.py` — add `_EDIT_MALFORMED_HINT` template constant near the top; insert the third dispatch branch between the existing `extract_diff` branch and the `command is None` fallthrough.

## Steps

### Step 1: Add the lenient regexes and `_extract_path` to `harness/prompts.py`
- Define `_INTENT_RE`, `_EDIT_RE_LENIENT`, `_SR_RE_LENIENT` as the patterns documented in [architecture.md § Lenient Edit Parser](../2026-05-27-agentbook-outcome-loop-design/architecture.md).
- Define `_extract_path(block: str) -> str` returning the first non-empty pre-SEARCH line stripped of backticks/leading punct/trailing colon.

### Step 2: Extend `extract_edits` with the fallback branch
- Signature stays `def extract_edits(text: str) -> list[tuple[str, str, str]]:`.
- Fast path (existing strict `_EDIT_RE.findall` + `_SR_RE.finditer`) returns first if non-empty.
- Else: short-circuit on `not _INTENT_RE.search(text)` → return `[]`.
- Else: iterate `_EDIT_RE_LENIENT.finditer(text)`; for each block, recover `path` via `_extract_path(block)`; on miss, look at the line immediately preceding the opening fence (`pre[-1]`) and accept if it ends with `.py`/`.pyx`/`.pyi` and contains a `/`.
- Last resort (only if `edits == []` after the lenient branch): scan raw `_SR_RE_LENIENT.finditer(text)` and accept the path from the previous 4 lines using the same allow-list.
- Return list of `(path, search, replace)` tuples. No new external imports.

### Step 3: Add `looks_like_edit_intent` and `diagnose_edit_block`
- Signatures: `def looks_like_edit_intent(text: str) -> bool` and `def diagnose_edit_block(text: str) -> str`.
- Bodies follow the architecture spec — the diagnostics classify "missing closing triple-backtick", "missing ======= separator", "missing >>>>>>> REPLACE marker (block looks truncated)", "missing opening ```edit fence", or the catch-all "malformed edit block (could not isolate SEARCH/REPLACE pair)".

### Step 4: Define `_EDIT_MALFORMED_HINT` in `harness/agent_loop.py`
- Add a single multi-line template constant near the top (sibling to `_NO_BLOCK_HINT`).
- The template MUST format with one positional `{diag}` substitution and MUST NOT contain the literal substring `Respond with EXACTLY ONE ```bash` (the Feature-3 scenario explicitly forbids it leaking from `_NO_BLOCK_HINT` into this branch).

### Step 5: Insert the third dispatch branch
- Locate the existing `extract_diff` branch (around line 175). Immediately after it and before the `command is None` fallthrough, insert the malformed-edit branch from [architecture.md § agent_loop.py](../2026-05-27-agentbook-outcome-loop-design/architecture.md).
- The branch MUST: detect `looks_like_edit_intent(text)`, increment `consecutive_parse_failures`, append a diagnostic to `episode.notes` (≤ 300 chars), append a `{"role": "user", "content": _EDIT_MALFORMED_HINT.format(diag=...)}` message, fire the 6-strike abort by setting `episode.stop_reason = "parse_failures"` and breaking when the cap is reached, otherwise `continue` to the next turn.

### Step 6: Re-run the 26 tests in `harness/tests/test_search_replace.py`
- All 26 must pass. Wall time ≤ 2s. No new external dependencies.

### Step 7: Project-wide regression sweep
- Run the full `experiments/agentbook-ab/` pytest collection. Confirm no other test file regresses.

## Verification Commands

```bash
# All 26 search-replace tests pass
cd experiments/agentbook-ab && \
  uv run python -m pytest harness/tests/test_search_replace.py -q

# Full experiment-wide regression sweep
cd experiments/agentbook-ab && \
  uv run python -m pytest -q

# Wall-time budget check
cd experiments/agentbook-ab && time uv run python -m pytest -q

# Ruff lint passes on modified files
uv run ruff check --fix experiments/agentbook-ab/harness/prompts.py experiments/agentbook-ab/harness/agent_loop.py
```

## Success Criteria

- All 26 tests in `harness/tests/test_search_replace.py` PASS (15 existing + 11 new from task-002).
- `harness/prompts.py` exports `looks_like_edit_intent` and `diagnose_edit_block`; `extract_edits` keeps its existing signature; no other public symbol changes.
- `harness/agent_loop.py` carries the new `_EDIT_MALFORMED_HINT` constant and the malformed-edit branch; `consecutive_parse_failures` still increments under the new branch; 6-strike abort still fires.
- Ruff passes on both modified files.
- No new external Python dependencies.
- `extract_edits` is still O(text) on well-formed input (fast path unchanged); fallback enters only when `_INTENT_RE.search` matches and fast path returned [].
