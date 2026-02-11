# Task 018: Final Verification

**Area**: All
**Priority**: Required
**BDD Scenario**: All scenarios

## Objective

Run full test suite and linting to verify all changes.

## What to Implement

### Run All Tests

```bash
# Backend unit tests
uv run pytest tests/unit/ -v

# Agent tests
uv run pytest agent/tests/ -v

# Frontend tests
cd web && pnpm test

# Frontend build
cd web && pnpm build
```

### Run All Linting

```bash
# Python linting
uv run ruff check .
uv run ruff format --check .

# Frontend linting
cd web && pnpm lint
```

### Manual Verification

1. Start backend: `uv run uvicorn app.main:app --reload`
2. Test MCP endpoint rejects without auth
3. Test agent starts and runs cycle

## Success Criteria

- All unit tests pass
- All linting passes with no errors
- Frontend builds successfully
- MCP endpoint requires authentication
- Agent handles errors with backoff

## Dependencies

- Task 017 (dead code removed)
