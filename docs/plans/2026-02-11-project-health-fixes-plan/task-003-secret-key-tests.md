# Task 003: Write Secret Key Validation Tests

**Area**: Backend
**Priority**: High
**BDD Scenario**: Application starts with secret key (ref: Scenario 1), Application fails without secret key in production (ref: Scenario 2)

## Objective

Create tests that verify secret key validation on application startup.

## Files to Create

- `tests/unit/core/test_config_validation.py` (new)

## What to Implement

Create test cases:

1. **Test app starts with secret key in production mode**
   - Set `SECRET_KEY=secure-key` and `DEBUG=false`
   - Assert Settings initializes without error

2. **Test app fails without secret key in production**
   - Set `SECRET_KEY=""` and `DEBUG=false`
   - Assert Settings raises `ValueError` with message containing "SECRET_KEY"

3. **Test app allows missing secret key in debug mode**
   - Set `SECRET_KEY=""` and `DEBUG=true`
   - Assert Settings initializes without error

4. **Test app starts with specific secret key**
   - Set `SECRET_KEY=my-custom-key`
   - Assert `settings.secret_key == "my-custom-key"`

## Verification

```bash
uv run pytest tests/unit/core/test_config_validation.py -v
```

Expected: All tests **FAIL** (Red phase) - validation not implemented yet.

## Dependencies

None - independent test file

## BDD References

- Feature: Secret key must be set in production - Scenarios 1, 2, 3