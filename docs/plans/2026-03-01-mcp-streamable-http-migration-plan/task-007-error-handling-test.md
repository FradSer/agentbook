# Task 007: Error Handling Test

**Type**: test
**Depends-on**: task-006-v2-tools-impl

## Objective

Write tests for error handling over Streamable HTTP transport.

## BDD Scenarios

```gherkin
Scenario: JSON-RPC parse error returns proper response
  When client sends POST request with invalid JSON body
  Then response returns HTTP 400 Bad Request
  And response body contains JSON-RPC error with code -32700 (PARSE_ERROR)
  And error message describes the parse failure

Scenario: Invalid JSON-RPC message returns validation error
  When client sends POST request with:
    | body                                                    |
    | {"jsonrpc": "2.0", "method": "test", "id": null}        |
  Then response returns HTTP 400 Bad Request
  And response body contains JSON-RPC error with code -32602 (INVALID_PARAMS)

Scenario: Unsupported HTTP method returns 405
  When client sends PUT request to /mcp
  Then response returns HTTP 405 Method Not Allowed
  And response includes Allow header: "GET, POST, DELETE"
  And error body indicates method not supported

Scenario: Tool execution error returns JSON-RPC error
  Given client calls resolve tool with invalid parameters
  When handle_resolve() returns error response
  Then response contains JSON-RPC error in SSE stream or JSON body
  And error type is "invalid_input" with descriptive detail
  And session remains valid for subsequent requests

Scenario: Connection error does not crash server
  Given session "session-error" is active
  When unexpected exception occurs during message processing
  Then error is logged with exception details
  And session remains operational
  And server continues accepting new requests
  And error is returned to client in proper JSON-RPC format
```

## Files to Modify

- `tests/integration/test_mcp_streamable_http.py`

## Test Cases

1. **test_json_parse_error** - Invalid JSON returns -32700
2. **test_invalid_jsonrpc_message** - Invalid message returns -32602
3. **test_unsupported_http_method** - PUT returns 405
4. **test_tool_execution_error** - Tool error returns JSON-RPC error
5. **test_server_stability_on_error** - Server doesn't crash

## Verification

```bash
uv run pytest tests/integration/test_mcp_streamable_http.py -k "error" -v
# Expected: 5 failed (RED phase)
```

## Commit

```
test(mcp): add error handling tests for streamable http

Test JSON-RPC errors, HTTP errors, and server stability.
```