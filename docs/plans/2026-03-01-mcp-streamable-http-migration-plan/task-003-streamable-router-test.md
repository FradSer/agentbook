# Task 003: Streamable HTTP Router Test

**Type**: test
**Depends-on**: task-002-session-validation-impl

## Objective

Write integration tests for Streamable HTTP transport endpoint before implementation.

## BDD Scenarios

```gherkin
Scenario: POST request establishes new session
  When client sends POST request to /mcp with:
    | header       | value                                    |
    | Accept       | application/json, text/event-stream      |
    | Content-Type | application/json                         |
    | Authorization| Bearer sk-agentbook-valid-key            |
  And request body contains initialize JSON-RPC message
  Then response returns HTTP 200 OK
  And response includes "mcp-session-id" header with valid session ID
  And session ID contains only visible ASCII characters (0x21-0x7E)
  And response body contains server capabilities

Scenario: Stateless mode creates no session
  Given StreamableHTTPSessionManager is configured with stateless=true
  When client sends POST request to /mcp with initialize message
  Then response returns HTTP 200 OK
  And response does NOT include "mcp-session-id" header
  And each request is processed independently
  And no session state persists between requests

Scenario: Accept header validation for POST
  When client sends POST request to /mcp with:
    | header       | value                    |
    | Accept       | application/json         |
    | Content-Type | application/json         |
  Then response returns HTTP 406 Not Acceptable
  And error message indicates "Client must accept both application/json and text/event-stream"

Scenario: Content-Type validation for POST
  When client sends POST request to /mcp with:
    | header       | value                                    |
    | Accept       | application/json, text/event-stream      |
    | Content-Type | text/plain                               |
  Then response returns HTTP 415 Unsupported Media Type
  And error message indicates "Content-Type must be application/json"
```

## Files to Create

- `tests/integration/test_mcp_streamable_http.py`

## Test Cases

1. **test_post_establishes_session** - Happy path for session creation
2. **test_stateless_mode_no_session_header** - Stateless mode behavior
3. **test_accept_header_validation** - Returns 406 for invalid Accept
4. **test_content_type_validation** - Returns 415 for invalid Content-Type
5. **test_initialize_returns_server_capabilities** - MCP protocol compliance

## Test Fixtures Required

- `async_client` - httpx AsyncClient for HTTP requests
- `auth_headers` - Valid Authorization header with test API key
- `mcp_initialize_request` - JSON-RPC initialize message body

## Verification

```bash
uv run pytest tests/integration/test_mcp_streamable_http.py -v
# Expected: 5 failed (RED phase - tests should fail before implementation)
```

## Commit

```
test(mcp): add streamable http transport integration tests

Add tests for POST endpoint, session establishment, and header validation.
```