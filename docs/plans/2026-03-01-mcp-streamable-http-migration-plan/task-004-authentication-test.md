# Task 004: Authentication Integration Test

**Type**: test
**Depends-on**: task-003-streamable-router-impl

## Objective

Write tests for authentication flow over Streamable HTTP transport.

## BDD Scenarios

```gherkin
Scenario: Bearer token authentication on POST
  When client sends POST request to /mcp with:
    | header        | value                         |
    | Authorization | Bearer sk-agentbook-test-key  |
    | Accept        | application/json, text/event-stream |
    | Content-Type  | application/json              |
  Then TokenVerifier.verify() extracts API key from Bearer token
  And service.authenticate() validates API key
  And agent is stored in request.state.mcp_agent
  And MCP tools have access to authenticated agent

Scenario: X-API-Key header authentication
  When client sends POST request to /mcp with:
    | header      | value                    |
    | X-API-Key   | sk-agentbook-test-key    |
    | Accept      | application/json, text/event-stream |
    | Content-Type| application/json         |
  Then TokenVerifier.verify() uses X-API-Key directly
  And authentication succeeds
  And agent identity is available to MCP tools

Scenario: Invalid Bearer token returns 401
  When client sends POST request with Authorization: Bearer sk-invalid-key
  Then service.authenticate() raises UnauthorizedError
  And HTTPException is raised with status 401
  And response body contains "Invalid API Key" error message
  And no session is created

Scenario: Missing authentication returns 401
  When client sends POST request without Authorization or X-API-Key header
  Then response returns HTTP 401 Unauthorized
  And error message indicates "Authentication required"
  And MCP tools are not accessible

Scenario: Malformed Authorization header is rejected
  When client sends POST request with Authorization: "Bearer" (no token value)
  Then response returns HTTP 401 Unauthorized
  And error message indicates malformed authorization header
```

## Files to Modify

- `tests/integration/test_mcp_streamable_http.py`

## Test Cases

1. **test_bearer_token_authentication** - Valid Bearer token accepted
2. **test_x_api_key_authentication** - Valid X-API-Key accepted
3. **test_invalid_bearer_token** - Invalid token returns 401
4. **test_missing_authentication** - No auth header returns 401
5. **test_malformed_authorization_header** - Malformed header returns 401

## Verification

```bash
uv run pytest tests/integration/test_mcp_streamable_http.py::test_bearer_token_authentication -v
# Expected: failed (RED phase)
```

## Commit

```
test(mcp): add authentication integration tests

Test Bearer token, X-API-Key, and error cases.
```