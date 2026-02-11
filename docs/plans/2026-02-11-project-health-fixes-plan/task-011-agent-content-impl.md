# Task 011: Implement Agent Content Rules Tests

**Area**: Agent
**Priority**: High
**BDD Scenario**: Content rules filter low-quality submissions (ref: Scenarios 1-3)

## Objective

Implement ContentRules if not already present, or verify existing implementation works correctly.

## Files to Modify

- `agent/src/rules.py` (if changes needed)

## What to Implement

Verify `ContentRules` has the following methods:

1. `check_thread(title: str, body: str) -> tuple[str, str]`
   - Returns `("reject", reason)` for empty/short content
   - Returns `("pass", "")` for valid content

2. `check_comment(content: str) -> tuple[str, str]`
   - Similar validation for comments

If methods are missing, implement them with:
- Minimum title length check (empty titles rejected)
- Minimum body length check (at least 20 characters)
- Spam keyword detection

## Verification

```bash
uv run pytest agent/tests/test_rules.py -v
```

Expected: All tests **PASS** (Green phase).

## Dependencies

**task-010-agent-content-tests.md** - Tests must exist first

## BDD References

- Feature: Content rules filter low-quality submissions - Scenarios 1, 2, 3