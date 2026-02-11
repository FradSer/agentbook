# Task 008: Write Agent Session Management Tests

**Area**: Agent
**Priority**: High
**BDD Scenario**: Session is closed after cycle, Session is closed on error

## Objective

Create tests verifying SQLAlchemy sessions are properly managed.

## Files to Create

- `agent/tests/test_session.py` (new)

## What to Implement

Create test cases:

1. **Test session is closed after successful cycle**
   - Mock SessionFactory with tracking
   - Run a successful review cycle
   - Assert session.close() was called

2. **Test session is closed on error**
   - Mock SessionFactory to raise exception during processing
   - Assert session.close() is still called (context manager behavior)

3. **Test session is committed on success**
   - Mock session.commit
   - Run successful cycle
   - Assert commit was called

## Verification

```bash
uv run pytest agent/tests/test_session.py -v
```

Expected: All tests **FAIL** (Red phase) - context manager not used yet.

## Dependencies

- Task 007 (backoff implemented)
