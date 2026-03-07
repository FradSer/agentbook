# Task 002: Session ID Validation Test

**Type**: test
**Depends-on**: task-001-config-mcp-transport

## Objective

Write unit tests for session ID validation functions before implementation.

## BDD Scenario

```gherkin
Scenario: Session ID is cryptographically secure
  Given session is established with ID "session-test"
  Then session ID is at least 32 characters
  And session ID uses secrets module for generation
  And session ID contains only visible ASCII characters (0x21-0x7E)
```

## Files to Create

- `tests/unit/test_session_validation.py`

## Test Cases

1. **Test valid session ID format**
   - Input: Session ID with visible ASCII characters (0x21-0x7E)
   - Expected: Returns `True`

2. **Test invalid session ID - too short**
   - Input: Session ID with 7 characters
   - Expected: Returns `False`

3. **Test invalid session ID - too long**
   - Input: Session ID with 129 characters
   - Expected: Returns `False`

4. **Test invalid session ID - contains whitespace**
   - Input: Session ID with space character
   - Expected: Returns `False`

5. **Test invalid session ID - contains control character**
   - Input: Session ID with null byte
   - Expected: Returns `False`

6. **Test session ID generation**
   - Call `generate_session_id()` 100 times
   - Assert all IDs are unique
   - Assert all IDs are 32 characters
   - Assert all IDs match pattern `[\x21-\x7E]+`

7. **Test session ID with None input**
   - Input: `None`
   - Expected: Returns `True` (no session ID is valid for new connections)

## Verification

```bash
uv run pytest tests/unit/test_session_validation.py -v
# Expected: 7 passed
```

## Commit

```
test(mcp): add session id validation unit tests

Test cases for session ID format validation and generation.
```