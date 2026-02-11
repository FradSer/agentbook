# Task 013: Add CORS Warning

**Area**: Configuration
**Priority**: Medium
**BDD Scenario**: Wildcard CORS in production logs warning

## Objective

Log a warning when CORS is set to wildcard in production mode.

## Files to Modify

- `app/core/config.py`

## What to Implement

### Add CORS Warning in Settings

In the Settings class validation:

1. Add import for logging: `import logging`
2. Add logger: `logger = logging.getLogger(__name__)`
3. In `__post_init__` or validator:
   - If `cors_allow_origins == "*"` AND `debug == False`
   - Log warning: `"CORS_ALLOW_ORIGINS='*' allows all origins. Consider restricting this in production."`

## Verification

```bash
# Run config tests
uv run pytest tests/unit/core/test_config_validation.py -v

# Manual verification
DEBUG=false CORS_ALLOW_ORIGINS='*' uv run python -c "from app.core.config import Settings; Settings()"
```

Expected: Warning logged to stderr.

## Dependencies

- Task 012 (railway config done)
