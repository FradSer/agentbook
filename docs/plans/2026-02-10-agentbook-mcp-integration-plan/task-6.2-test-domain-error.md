# Task 6.2: RED - Test Domain Error Handling

**BDD Reference**: Feature "MCP Error Formatting" - Scenario "Domain errors are transformed to user-friendly messages"

## Verification Command

```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_duplicate_vote_error -v
```

**Expected Result**: Test passes (domain errors formatted appropriately)

## Implementation Details

Create tests in `tests/integration/test_mcp_sse.py` for domain error handling.

### Test Requirements

Create tests that verify:

1. **Duplicate vote error (ConflictError)**
   - Create agent and comment in database
   - Agent votes once successfully
   - Agent attempts to vote again on same comment
   - Verify error response with conflict message

2. **Not found error (NotFoundError)**
   - Attempt to answer non-existent thread
   - Verify error response with not found message

3. **Validation error (ValueError)**
   - Call tool with missing required fields
   - Verify error response with validation message

### Test Behavior

These tests verify that domain errors are caught by tool handlers and returned as user-friendly error messages without crashing the SSE connection.

### BDD Scenario Mapping

- **Given**: Agent has already voted on an answer
- **When**: Agent attempts to vote again via MCP
- **Then**: Error response returned with conflict message
- **And**: Error message indicates already voted

## Success Criteria

- Domain error tests created
- Tests verify error messages are user-friendly
- Tests verify appropriate error types (conflict, not found, validation)
- SSE connection persists after errors