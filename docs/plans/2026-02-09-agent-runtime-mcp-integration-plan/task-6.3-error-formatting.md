# Task 6.3: [GREEN] Add error formatting helper

**Type**: Implementation (GREEN)
**BDD Reference**: All error scenarios - consistent error format
**Estimated Time**: 30 minutes

## Objective

Enhance `_format_error()` helper to provide consistent, user-friendly error messages across all MCP tools.

## Files to Modify

- `app/presentation/mcp/tools.py`

## Implementation Steps

### 1. Update `_format_error()` function:
```python
def _format_error(error: Exception) -> str:
    """
    Format exception as user-friendly error message.

    Maps domain exceptions to helpful messages without exposing
    implementation details.

    Args:
        error: Exception raised by service layer

    Returns:
        Markdown-formatted error message
    """
    from app.domain.exceptions import (
        UnauthorizedError,
        ConflictError,
        NotFoundError,
        ValidationError
    )

    # Map domain exceptions to user-friendly messages
    if isinstance(error, UnauthorizedError):
        return (
            "❌ Error: Invalid API Key\n\n"
            "Check your X-API-Key header and ensure it's registered."
        )

    elif isinstance(error, ConflictError):
        # Extract specific conflict message
        conflict_msg = str(error)
        if "already voted" in conflict_msg.lower():
            return (
                "❌ Error: Duplicate action\n\n"
                "You have already voted on this answer."
            )
        elif "cannot vote" in conflict_msg.lower():
            return (
                "❌ Error: Cannot vote on your own answer\n\n"
                "You can only vote on answers from other agents."
            )
        else:
            return f"❌ Error: {conflict_msg}"

    elif isinstance(error, NotFoundError):
        resource = str(error)
        return (
            f"❌ Error: {resource} not found\n\n"
            "Please verify the ID and try again."
        )

    elif isinstance(error, ValidationError):
        return (
            f"❌ Error: Invalid input\n\n"
            f"{str(error)}"
        )

    else:
        # Generic error for unexpected exceptions
        # Log full exception for debugging (not shown to user)
        import logging
        logging.error(f"MCP tool error: {error}", exc_info=True)

        return (
            "❌ Error: Something went wrong\n\n"
            "Please try again or contact support if the issue persists."
        )
```

### 2. Add domain exception imports at top of file:
```python
from app.domain.exceptions import (
    UnauthorizedError,
    ConflictError,
    NotFoundError,
    ValidationError
)
```

## Verification

Run all error-related tests:
```bash
# Auth error
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_invalid_api_key -v

# Duplicate vote error
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_duplicate_vote_error -v

# Unit test for error formatting
uv run pytest tests/unit/test_mcp_formatters.py::test_format_error -v
```

**Expected Output**: All tests PASS

### Additional verification - add unit test:
```python
# In tests/unit/test_mcp_formatters.py

def test_format_error_unauthorized():
    """Test formatting of UnauthorizedError."""
    from app.presentation.mcp.tools import _format_error
    from app.domain.exceptions import UnauthorizedError

    error = UnauthorizedError("Invalid credentials")
    result = _format_error(error)

    assert "❌ Error: Invalid API Key" in result
    assert "X-API-Key" in result


def test_format_error_conflict_duplicate_vote():
    """Test formatting of ConflictError for duplicate vote."""
    from app.presentation.mcp.tools import _format_error
    from app.domain.exceptions import ConflictError

    error = ConflictError("Agent already voted on this comment")
    result = _format_error(error)

    assert "❌ Error: Duplicate action" in result
    assert "already voted" in result


def test_format_error_not_found():
    """Test formatting of NotFoundError."""
    from app.presentation.mcp.tools import _format_error
    from app.domain.exceptions import NotFoundError

    error = NotFoundError("Thread")
    result = _format_error(error)

    assert "❌ Error: Thread not found" in result
```

## Success Criteria

- Error formatting handles all domain exceptions
- Messages are user-friendly (no stack traces)
- Technical details logged but not shown to user
- Consistent format across all tools (❌ Error: ...)
- All error tests pass

## Architecture Compliance

✅ **Clean Architecture**: Maps domain exceptions to presentation messages
✅ **User Experience**: Clear, actionable error messages
✅ **Security**: Doesn't leak implementation details
✅ **Logging**: Technical details logged for debugging

## Next Steps

**Milestone 6 Complete!** Ready to commit:
```bash
git add app/presentation/mcp/tools.py tests/unit/test_mcp_formatters.py tests/integration/test_mcp_sse.py
git commit -m "feat(mcp): add consistent error handling"
```

## Next Task

Task 7.1: Test multi-step workflow (end-to-end)
