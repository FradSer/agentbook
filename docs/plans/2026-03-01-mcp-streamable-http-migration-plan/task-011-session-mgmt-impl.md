# Task 011: Session Management Implementation

**Type**: impl
**Depends-on**: task-011-session-mgmt-test

## Objective

Implement session lifecycle management for Streamable HTTP transport.

## BDD Scenario

```gherkin
Scenario: DELETE request terminates session explicitly
  Given client has active session with ID "session-terminate-test"
  When client sends DELETE request to /mcp with:
    | header          | value                       |
    | mcp-session-id  | session-terminate-test      |
  Then response returns HTTP 200 OK
  And session is marked as terminated
  And all associated streams are closed
  And subsequent requests with same session ID return HTTP 404 Not Found
```

## Files to Modify

- `app/presentation/mcp/streamable_router.py`

## Implementation Steps

1. Add DELETE handler in `mcp_endpoint`:
   - Extract session ID from header
   - Call session manager termination
   - Return 200 OK on success

2. Add session validation in POST handler:
   - Check if session ID exists
   - Return 404 if invalid/expired

3. Implement graceful shutdown:
   - Cancel all session tasks on lifespan exit
   - Close all memory streams
   - Clear session references

## Verification

```bash
uv run pytest tests/integration/test_mcp_streamable_http.py -k "session" -v
# Expected: 5 passed
```

## Commit

```
feat(mcp): implement session lifecycle management

Add DELETE termination, invalid session handling, and cleanup on shutdown.
```