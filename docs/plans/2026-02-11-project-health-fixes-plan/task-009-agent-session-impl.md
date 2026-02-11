# Task 009: Implement Agent Session Management

**Area**: Agent
**Priority**: High
**BDD Scenario**: Session is closed after cycle, Session is closed on error

## Objective

Use context manager for SQLAlchemy sessions to ensure proper cleanup.

## Files to Modify

- `agent/src/main.py`

## What to Implement

### Update Main Loop Session Handling

In the `main()` function:

1. Change `session_factory = SessionFactory` to use context manager pattern
2. Wrap the cycle processing in `with SessionFactory() as session:`
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

- Task 008 (tests must exist first)
