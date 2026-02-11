# Task 021: Remove Dead Code

**Area**: All
**Priority**: Low
**BDD Scenario**: N/A (code cleanup)

## Objective

Remove unused functions and imports identified in health check.

## Files to Modify

- `app/presentation/mcp/tools.py` - Remove `_format_error()` function
- `app/presentation/mcp/auth.py` - Remove unused `hash_api_key` import
- `agent/src/rules.py` - Remove `is_duplicate()` method
- `agent/src/config.py` - Remove unused `DATA_DIR` and `STATE_DB` paths

## What to Implement

### Backend (tools.py)

Delete the `_format_error()` function - it is never called.

### Backend (auth.py)

Remove the import line:
```python
from app.infrastructure.security import hash_api_key
```

### Agent (rules.py)

Delete the `is_duplicate()` method if it exists and is unused.

### Agent (config.py)

Delete unused path definitions:
```python
DATA_DIR = AGENT_ROOT / "data"
STATE_DB = DATA_DIR / "agent_state.db"
```

## Verification

```bash
# Run all tests to ensure nothing breaks
uv run pytest tests/unit/ -v
uv run pytest agent/tests/ -v

# Run ruff to check for any issues
uv run ruff check .
```

Expected: All tests pass, no ruff errors.

## Dependencies

None - independent cleanup

## BDD References

None - code cleanup