# Task 005: Add Embedding Error Logging

**Area**: Backend
**Priority**: Medium
**BDD Scenario**: Embedding failure is logged (ref: Scenario 1)

## Objective

Ensure embedding failures are logged instead of silently swallowed.

## Files to Modify

- `app/infrastructure/embeddings/openrouter.py` (or equivalent file with `_safe_embed`)

## What to Implement

### Add Logging to Exception Handler

In the embedding error handling code:

1. Find the exception handler that catches embedding errors
2. Add logging call:
   - Log level: `logger.warning()`
   - Include the error message
   - Indicate fallback is being used

Example pattern:
```python
except Exception as e:
    logger.warning(f"Embedding failed, using fallback: {e}")
    return None
```

## Verification

```bash
# Run existing tests to ensure no regressions
uv run pytest tests/unit/ -v -k embed
```

Expected: Tests pass. Manual verification by checking logs when OpenRouter is unavailable.

## Dependencies

None - independent change

## BDD References

- Feature: All errors are logged - Scenario 1