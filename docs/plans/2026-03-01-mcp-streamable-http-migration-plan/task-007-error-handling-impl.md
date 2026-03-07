# Task 007: Error Handling Implementation

**Type**: impl
**Depends-on**: task-007-error-handling-test

## Objective

Implement proper error handling for Streamable HTTP transport.

## BDD Scenario

```gherkin
Scenario: JSON-RPC parse error returns proper response
  When client sends POST request with invalid JSON body
  Then response returns HTTP 400 Bad Request
  And response body contains JSON-RPC error with code -32700 (PARSE_ERROR)
  And error message describes the parse failure

Scenario: Unsupported HTTP method returns 405
  When client sends PUT request to /mcp
  Then response returns HTTP 405 Method Not Allowed
  And response includes Allow header: "GET, POST, DELETE"
```

## Files to Modify

- `app/presentation/mcp/streamable_router.py`

## Implementation Steps

1. Add JSON-RPC error code constants:
   ```python
   PARSE_ERROR = -32700
   INVALID_REQUEST = -32600
   METHOD_NOT_FOUND = -32601
   INVALID_PARAMS = -32602
   INTERNAL_ERROR = -32603
   ```

2. Create error response helper:
   ```python
   def create_jsonrpc_error(code: int, message: str, request_id: Any = None) -> dict:
       return {
           "jsonrpc": "2.0",
           "error": {"code": code, "message": message},
           "id": request_id
       }
   ```

3. Add HTTP method validation in `mcp_endpoint`:
   - Allow only POST, GET, DELETE
   - Return 405 with Allow header for other methods

4. Add exception handling around session manager delegation:
   - Catch JSON parse errors → return -32700
   - Catch validation errors → return -32602
   - Catch unexpected errors → return -32603, log error

## Verification

```bash
uv run pytest tests/integration/test_mcp_streamable_http.py -k "error" -v
# Expected: 5 passed
```

## Commit

```
feat(mcp): implement error handling for streamable http transport

Add JSON-RPC error codes, HTTP method validation, and exception handling.
```