# Task 001: Write MCP Authentication Tests

**Area**: Backend
**Priority**: Critical
**BDD Scenario**: MCP tool call without authentication (ref: Scenario 1), MCP tool call with invalid API key (ref: Scenario 2)

## Objective

Create test cases that verify MCP endpoints reject unauthenticated requests.

## Files to Create

- `tests/unit/presentation/mcp/test_auth.py` (new)

## What to Implement

Create a test file with the following test cases:

1. **Test SSE connection rejected without Authorization header**
   - Mock an SSE connection request without any auth headers
   - Assert response is 401 Unauthorized

2. **Test SSE connection rejected with invalid Bearer token**
   - Mock an SSE connection with `Authorization: Bearer invalid-key`
   - Assert response is 401 Unauthorized

3. **Test SSE connection rejected with non-prefixed API key**
   - Mock an SSE connection with `Authorization: Bearer some-random-string`
   - Assert response is 401 Unauthorized

4. **Test tool call fails without authenticated agent in context**
   - Mock tool invocation when `server._agent` is the placeholder
   - Assert tool raises authentication error

## Verification

```bash
uv run pytest tests/unit/presentation/mcp/test_auth.py -v
```

Expected: All tests **FAIL** (Red phase) - no auth enforcement exists yet.

## Dependencies

None - this is the first task.

## BDD References

- Scenario 1: MCP tool call without authentication
- Scenario 2: MCP tool call with invalid API key