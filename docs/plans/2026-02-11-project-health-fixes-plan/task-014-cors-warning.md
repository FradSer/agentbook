# Task 014: Add CORS Warning

**Area**: Configuration
**Priority**: Medium
**BDD Scenario**: Wildcard CORS in production logs warning (ref: Scenario 1)

## Objective

Add warning when permissive CORS setting is used in production.

## Files to Modify

- `app/core/config.py`

## What to Implement

### Add CORS Warning to __post_init__

In the `Settings.__post_init__` method, add logging:

```python
if self.cors_allow_origins == "*" and not self.debug:
    logger.warning(
        "CORS_ALLOW_ORIGINS='*' allows all origins. "
        "Consider restricting this in production."
    )
```

Also update `.env.example` to document the CORS configuration option.

## Verification

```bash
# Run unit tests to ensure config still works
uv run pytest tests/unit/core/test_config_validation.py -v
```

Expected: Tests pass.

## Dependencies

None - independent change to config validation

## BDD References

- Feature: Permissive CORS triggers warning - Scenarios 1, 2