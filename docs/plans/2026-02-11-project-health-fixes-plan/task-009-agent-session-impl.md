# Task 009: Implement Agent Session Management

**Area**: Agent
**Priority**: High
**BDD Scenario**: Session is closed after cycle (ref: Scenario 1), Session is closed on error (ref: Scenario 2)

## Objective

Use context manager for SQLAlchemy sessions to ensure proper cleanup.

## Files to Modify

- `agent/src/main.py`

## What to Implement

### Update Main Loop Session Handling

In the `main()` function:

1. Change session handling to use context manager pattern: `with SessionFactory() as session:`
2. Wrap the cycle processing inside the context manager
3. Update `create_service()` call to pass session correctly
4. Add explicit `session.commit()` after successful processing

### Update create_service Function

Modify to accept session directly instead of factory:
- `create_service(session)` instead of `create_service(session_factory)`
- Repositories use the passed session directly

## Verification

```bash
uv run pytest agent/tests/test_session.py -v
```

Expected: All tests **PASS** (Green phase).

## Dependencies

**task-008-agent-session-tests.md** - Tests must exist first

## BDD References

- Feature: SQLAlchemy sessions are properly managed - Scenarios 1, 2