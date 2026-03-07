# Task 003: Streamable HTTP Router Implementation

**Type**: impl
**Depends-on**: task-003-streamable-router-test

## Objective

Implement Streamable HTTP router that passes all integration tests.

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
```

## Files to Create

- `app/presentation/mcp/streamable_router.py`

## Files to Modify

- `app/main.py` - Import and mount streamable router

## Implementation Steps

1. Create `streamable_router.py` with:
   - Global `_session_manager` and `_mcp_server` references
   - `setup_streamable_mcp(service, service_v2)` function
   - `create_mcp_app()` function returning Starlette app
   - Session manager configuration from settings

2. Implement `mcp_endpoint` handler:
   - Validate Accept header (must include both json and event-stream)
   - Validate Content-Type header (must be application/json)
   - Extract and verify authentication
   - Delegate to session manager

3. Integrate with `main.py`:
   - Import `setup_streamable_mcp` and `create_mcp_app`
   - Call `setup_streamable_mcp` in lifespan
   - Mount `/mcp` endpoint when `mcp_transport` is "streamable_http" or "both"

## Key Implementation Details

- Use `StreamableHTTPSessionManager` from `mcp.server.streamable_http_manager`
- Configure `stateless=True` and `json_response=True` from settings
- Session manager must run in lifespan context manager

## Verification

```bash
uv run pytest tests/integration/test_mcp_streamable_http.py -v
# Expected: 5 passed (GREEN phase - tests should pass)
```

## Commit

```
feat(mcp): implement streamable http transport router

Add StreamableHTTPSessionManager integration with FastAPI lifespan.
Supports stateless mode and JSON response configuration.
```