# Task 6.1: RED - Test Authentication Error Handling

**BDD Reference**: Feature "MCP Authentication" - Scenario "Missing Bearer token returns 401 error"

## Verification Command

```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_auth_required -v
```

**Expected Result**: Test passes (FastMCP's built-in auth handles missing tokens)

## Implementation Details

Create tests in `tests/integration/test_mcp_sse.py` for authentication error handling.

### Test Requirements

Create tests that verify:

1. **Missing Bearer token**
   - Send GET request to /mcp/sse without Authorization header
   - Verify HTTP 401 status code
   - Verify error message indicates authentication required

2. **Invalid Bearer token**
   - Send GET request to /mcp/sse with invalid Bearer token
   - Verify HTTP 401 status code
   - Verify error message indicates invalid credentials

### Test Behavior

These tests verify that FastMCP's built-in BearerAuthBackend and RequireAuthMiddleware properly handle authentication failures before any service methods are called.

### BDD Scenario Mapping

- **Given**: Agent attempts to connect without Bearer token
- **When**: SSE connection request sent to /mcp/sse
- **Then**: Connection is rejected with 401 status
- **And**: Error message indicates authentication required

## Success Criteria

- Authentication error tests created
- Tests verify 401 status for missing/invalid tokens
- Tests verify user-friendly error messages
- No service methods called on auth failure