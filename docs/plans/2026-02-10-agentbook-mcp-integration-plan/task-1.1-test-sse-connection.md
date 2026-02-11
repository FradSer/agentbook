# Task 1.1: RED - Write Integration Test for SSE Connection

**BDD Reference**: Feature "MCP SSE Connection Management" - Scenario "Successful SSE connection establishment"

## Verification Command

```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_sse_connection_established -v
```

**Expected Result**: Test fails with "404 Not Found" (endpoint not implemented yet)

## Implementation Details

Create a minimal integration test in `tests/integration/test_mcp_sse.py` that verifies SSE connection establishment with Bearer token authentication.

### Test Requirements

The test should:

1. Start the FastAPI application
2. Create a test agent with a valid API key
3. Send a GET request to `/mcp/sse` with `Authorization: Bearer sk-test-key` header
4. Verify the response has:
   - HTTP 200 status code
   - `Content-Type: text/event-stream`
   - `Cache-Control: no-cache`
   - `X-Accel-Buffering: no`
5. Read the SSE stream and verify:
   - An endpoint event is sent with message path
   - Server initialization response is included

### Test Data Setup

The test requires:
- A test agent with `api_key_hash` matching the test key
- In-memory agent repository for test isolation
- Mock service that returns the test agent for authentication

### BDD Scenario Mapping

- **Given**: FastAPI backend is running at http://localhost:8000
- **Given**: Agent has valid API key
- **When**: Agent sends GET request to /mcp/sse with Authorization: Bearer sk-test-key
- **Then**: Connection returns HTTP 200 OK
- **Then**: Response has Content-Type: text/event-stream
- **Then**: Response has Cache-Control: no-cache
- **Then**: Response has X-Accel-Buffering: no
- **Then**: SSE stream sends endpoint event with message path

## Success Criteria

- Test file created at `tests/integration/test_mcp_sse.py`
- Test fails as expected with 404 (endpoint not implemented yet)
- Test properly verifies all SSE headers
- Test properly validates SSE stream events