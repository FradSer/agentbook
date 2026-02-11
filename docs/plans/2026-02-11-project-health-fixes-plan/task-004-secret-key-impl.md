# Task 004: Implement Secret Key Validation

**Area**: Backend
**Priority**: High
**BDD Scenario**: Application fails without secret key in production (ref: Scenario 2)

## Objective

Add validation that requires SECRET_KEY in production environments.

## Files to Modify

- `app/core/config.py`

## What to Implement

### Add Post-Initialization Validation

In `Settings` class:

1. Change `secret_key` default from `"change-me"` to empty string `""`

2. Add `__post_init__` method or use Pydantic validator:
   - If `secret_key` is empty AND `debug` is `False`
   - Raise `ValueError("SECRET_KEY must be set in production")`

3. Empty secret key is allowed when `debug=True` for development

## Verification

```bash
uv run pytest tests/unit/core/test_config_validation.py -v
```

Expected: All tests **PASS** (Green phase).

## Dependencies

**task-003-secret-key-tests.md** - Tests must exist first

## BDD References

- Feature: Secret key must be set in production - Scenario 2