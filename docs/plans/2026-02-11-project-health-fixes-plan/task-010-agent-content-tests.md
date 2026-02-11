# Task 010: Write Agent Content Rules Tests

**Area**: Agent
**Priority**: High
**BDD Scenario**: Empty title is rejected, Short body is rejected, Valid content passes

## Objective

Create tests for ContentRules validation.

## Files to Create

- `agent/tests/test_rules.py` (new)

## What to Implement

Create test cases for `ContentRules`:

1. **Test empty title is rejected**
   - Call `ContentRules.check_thread("", "some body")`
   - Assert result is `"reject"`
   - Assert reason contains "empty" (case insensitive)

2. **Test short body is rejected**
   - Call `ContentRules.check_thread("Title", "short")`
   - Assert result is `"reject"`

3. **Test valid content passes**
   - Call `ContentRules.check_thread("Valid Question", "This is a valid body with enough content.")`
   - Assert result is `"pass"`

4. **Test comment content validation**
   - Call `ContentRules.check_comment()` with various inputs
   - Verify rejection of empty/short content

## Verification

```bash
uv run pytest agent/tests/test_rules.py -v
```

Expected: Tests **PASS** - ContentRules already implemented correctly (existing code verification).

## Dependencies

- Task 009 (session management done)
