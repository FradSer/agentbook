# Task 008 — Implement: Synchronous Quality Gate

**Type:** Green (implementation)
**Depends-on:** task-007
**BDD refs:** Feature 2 Scenario "Synchronous quality guardrails reject gibberish", Feature 6 Scenario "Spam and gibberish caught by synchronous quality check"

## Goal

Implement the synchronous quality gate in `app/domain/quality.py`. Pure functions, no I/O, no LLM calls.

## What to implement

### `check_problem_quality(description, error_signature) -> tuple[bool, str | None]`

Checks in order (short-circuit on first failure):
1. Strip whitespace; if length < 20 → reject with "Problem description too short"
2. Check character diversity: if unique chars / total chars < 0.2 → reject as gibberish
3. Check spam patterns: compile a small set of regex patterns for known spam signals ("buy", "click here", pure URLs) → reject as "spam_detected"
4. Return `(True, None)` if all checks pass

### `check_solution_quality(content, steps) -> tuple[bool, str | None]`

Checks in order:
1. Strip whitespace; if empty → reject with "Solution content cannot be empty"
2. If `len(content) < 10` and `not steps` → reject as "Solution too short"
3. Spam pattern check (same patterns as above)
4. Return `(True, None)` if all checks pass

### Design constraints
- All regex patterns compiled at module load (not per call)
- No external dependencies
- Function must handle `None` inputs gracefully (treat as empty string)

## Files to create

- `app/domain/quality.py`

## Verification

```bash
uv run pytest tests/unit/test_quality_gate.py -v
```

All tests from task-007 must pass (green).
