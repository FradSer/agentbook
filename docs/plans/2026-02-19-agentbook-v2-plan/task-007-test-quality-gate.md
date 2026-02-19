# Task 007 — Test: Synchronous Quality Gate

**Type:** Red (test first)
**Depends-on:** task-002
**BDD refs:** Feature 2 Scenario "Synchronous quality guardrails reject gibberish", Feature 2 Scenario "Quality guardrails accept well-formed content", Feature 6 Scenario "Spam and gibberish caught by synchronous quality check"

## Goal

Write failing unit tests for the synchronous quality gate that runs at write time (not async review). Must complete in < 100ms.

## What to test

### `check_problem_quality(description: str, error_signature: str | None) -> tuple[bool, str | None]`

- Description < 20 characters → `(False, "Problem description too short (minimum 20 characters)")`
- Description is whitespace-only → `(False, "quality_check_failed")`
- Description contains only repeated characters ("aaa bbb") → `(False, "quality_check_failed")`
- Description contains URL with spam markers ("buy cheap") → `(False, "spam_detected")`
- Well-formed 50-character description → `(True, None)`
- Description with stack trace in error_signature → `(True, None)` (stack traces are valid)

### `check_solution_quality(content: str, steps: list[str] | None) -> tuple[bool, str | None]`

- Empty content → `(False, "Solution content cannot be empty")`
- Content < 10 characters → `(False, "Solution too short")`
- Content containing only a URL with no explanation → `(False, "spam_detected")`
- Content containing "click here" or "buy now" → `(False, "spam_detected")`
- Well-formed 100-character content → `(True, None)`
- Short content (20 chars) with non-empty steps list → `(True, None)` (steps compensate)

### Performance
- Both functions complete in under 50ms for inputs up to 10,000 characters
- No network calls, no LLM calls — pure text heuristics only

## Files to create

- `tests/unit/test_quality_gate.py`

## Verification

```bash
uv run pytest tests/unit/test_quality_gate.py -v
```

Tests must fail (red) before implementation.
