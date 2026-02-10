# Task 6.3: GREEN - Add Error Formatting Helper

**BDD Reference**: Feature "MCP Error Formatting" - All scenarios

## Verification Command
```bash
# Run all error-related tests
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_duplicate_vote_error -v
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_auth_required -v
```

**Expected Result**: All error tests pass with user-friendly error messages

## Implementation Notes

Add to `app/presentation/mcp/tools.py`:

```python
def _format_error(error: Exception) -> str:
    """Format error message for MCP response.

    Args:
        error: Exception to format

    Returns:
        User-friendly error message
    """
    return f"❌ Error: {str(error)}\n\nPlease try again or contact support."
```

Ensure all tool handlers use this formatter:

```python
@server.tool()
async def some_tool(...) -> str:
    try:
        # service call
        return _format_success(result)
    except NotFoundError as e:
        return _format_error(e)
    except ConflictError as e:
        return _format_error(e)
    except ValueError as e:
        return _format_error(e)
    except Exception as e:
        return _format_error(e)
```

Add error tests to `tests/unit/test_mcp_formatters.py`:

```python
def test_format_error() -> None:
    """Test error message formatting."""
    error = ValueError("Invalid query parameter")

    result = _format_error(error)

    assert "❌ Error:" in result
    assert "Invalid query parameter" in result
    assert "try again" in result.lower() or "contact" in result.lower()
```

## Success Criteria
- `_format_error()` helper function implemented
- All tool handlers use error formatter
- Error messages prefixed with "❌ Error:"
- Error messages include recovery suggestions
- All error tests pass