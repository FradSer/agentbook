# Task 6.3: GREEN - Add Error Formatting Helper

**BDD Reference**: Feature "MCP Error Formatting" - All scenarios

## Verification Command

```bash
# Run all error-related tests
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_duplicate_vote_error -v
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_auth_required -v
```

**Expected Result**: All error tests pass with user-friendly error messages

## Implementation Details

Add error formatting helper to `app/presentation/mcp/tools.py`.

### Helper Function Requirements

Create `_format_error()` function that:

1. Accepts an Exception object

2. Returns a formatted error message string with:
   - "❌ Error:" prefix
   - Exception message
   - Recovery suggestion text

### Tool Handler Requirements

Ensure all tool handlers use the error formatter:

1. Wrap service calls in try-except blocks

2. Catch specific domain errors:
   - NotFoundError
   - ConflictError
   - ValueError
   - General Exception as fallback

3. Return `_format_error(error)` for all caught exceptions

### Unit Test Requirements

Add test to `tests/unit/test_mcp_formatters.py`:

1. Verify error message format
2. Verify error prefix present
3. Verify recovery suggestion included

### BDD Scenario Mapping

- **Given**: Service raises domain exception
- **When**: MCP tool handler catches exception
- **Then**: Returns TextContent with error message
- **Then**: Error message includes "❌ Error:" prefix

## Success Criteria

- `_format_error()` helper function implemented
- All tool handlers use error formatter
- Error messages prefixed with "❌ Error:"
- Error messages include recovery suggestions
- All error tests pass