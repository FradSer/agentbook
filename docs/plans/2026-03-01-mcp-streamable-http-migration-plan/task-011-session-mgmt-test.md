# Task 011: Session Management Test

**Type**: test
**Depends-on**: task-003-streamable-router-impl

## Objective

Write tests for session lifecycle management over Streamable HTTP transport.

## BDD Scenarios

```gherkin
Scenario: Session persists across multiple requests
  Given client establishes session with ID "session-xyz"
  When client sends POST request with mcp-session-id: session-xyz
  And client sends another POST request with mcp-session-id: session-xyz
  Then both requests use same session state
  And server maintains connection context between requests

Scenario: DELETE request terminates session explicitly
  Given client has active session with ID "session-terminate-test"
  When client sends DELETE request to /mcp with:
    | header          | value                       |
    | mcp-session-id  | session-terminate-test      |
  Then response returns HTTP 200 OK
  And session is marked as terminated
  And all associated streams are closed
  And subsequent requests with same session ID return HTTP 404 Not Found

Scenario: Invalid session ID returns 404
  Given no session exists with ID "nonexistent-session"
  When client sends POST request with mcp-session-id: nonexistent-session
  Then response returns HTTP 404 Not Found
  And error message indicates "Invalid or expired session ID"

Scenario: Multiple sessions from same client
  Given client establishes session "session-a"
  When same client establishes another session "session-b"
  Then both sessions coexist independently
  And each session maintains separate state
  And requests to session-a do not affect session-b

Scenario: Session cleanup on server shutdown
  Given server has 5 active sessions
  When server initiates graceful shutdown
  Then all session tasks are cancelled
  And all memory streams are closed
  And no orphaned resources remain
```

## Files to Modify

- `tests/integration/test_mcp_streamable_http.py`

## Test Cases

1. **test_session_persists_across_requests** - Stateful session behavior
2. **test_delete_terminates_session** - DELETE method handling
3. **test_invalid_session_id_404** - Error handling for invalid sessions
4. **test_multiple_sessions_independent** - Session isolation
5. **test_session_cleanup_on_shutdown** - Graceful shutdown handling

## Verification

```bash
uv run pytest tests/integration/test_mcp_streamable_http.py -k "session" -v
# Expected: 5 failed (RED phase)
```

## Commit

```
test(mcp): add session management tests for streamable http

Test session persistence, termination, and cleanup scenarios.
```