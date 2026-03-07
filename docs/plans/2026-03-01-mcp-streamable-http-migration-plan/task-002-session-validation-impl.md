# Task 002: Session ID Validation Implementation

**Type**: impl
**Depends-on**: task-002-session-validation-test

## Objective

Implement session ID validation functions to pass all unit tests.

## BDD Scenario

```gherkin
Scenario: Session ID is cryptographically secure
  Given session is established with ID "session-test"
  Then session ID is at least 32 characters
  And session ID uses secrets module for generation
  And session ID contains only visible ASCII characters (0x21-0x7E)
```

## Files to Create

- `app/presentation/mcp/session.py`

## Implementation Steps

1. Create `validate_session_id(session_id: str | None) -> bool`:
   - Return `True` if session_id is `None` (valid for new connections)
   - Check length is between 8 and 128 characters
   - Check all characters are in range 0x21-0x7E (visible ASCII)
   - Use regex pattern for efficient validation

2. Create `generate_session_id(length: int = 32) -> str`:
   - Use `secrets.choice()` for cryptographic security
   - Generate string from characters 0x21-0x7E
   - Default length 32 characters

3. Create `SESSION_ID_PATTERN` regex:
   - Pattern: `^[\x21-\x7E]+$`
   - Pre-compile for performance

## Code Structure

```python
import re
import secrets

SESSION_ID_PATTERN = re.compile(r'^[\x21-\x7E]+$')
MIN_SESSION_ID_LENGTH = 8
MAX_SESSION_ID_LENGTH = 128
DEFAULT_SESSION_ID_LENGTH = 32

def validate_session_id(session_id: str | None) -> bool:
    ...

def generate_session_id(length: int = DEFAULT_SESSION_ID_LENGTH) -> str:
    ...
```

## Verification

```bash
uv run pytest tests/unit/test_session_validation.py -v
# Expected: 7 passed
```

## Commit

```
feat(mcp): implement session id validation and generation

Add cryptographic session ID generation and format validation.
```