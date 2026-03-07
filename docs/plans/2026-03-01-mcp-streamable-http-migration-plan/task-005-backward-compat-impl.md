# Task 005: Backward Compatibility Implementation

**Type**: impl
**Depends-on**: task-005-backward-compat-test

## Objective

Implement configuration-based transport selection to support both SSE and Streamable HTTP during migration.

## BDD Scenario

```gherkin
Scenario: Configuration toggle between transports
  Given configuration setting MCP_TRANSPORT=streamable_http
  When server starts
  Then only Streamable HTTP endpoint is mounted
  And SSE endpoint returns 404
  When configuration is changed to MCP_TRANSPORT=both
  And server restarts
  Then both endpoints are available
```

## Files to Modify

- `app/main.py`

## Implementation Steps

1. Import settings in `main.py`

2. Modify `create_app()` to conditionally mount transports:
   ```python
   # SSE transport (legacy)
   if settings.mcp_transport in ("sse", "both"):
       from app.presentation.mcp.router import setup_mcp_app, sse_router
       setup_mcp_app(service, service_v2)
       app.include_router(sse_router, prefix="/mcp")

   # Streamable HTTP transport (new)
   if settings.mcp_transport in ("streamable_http", "both"):
       from app.presentation.mcp.streamable_router import setup_streamable_mcp, create_mcp_app
       setup_streamable_mcp(service, service_v2)
       app.mount("/mcp", create_mcp_app())
   ```

3. Update lifespan to handle both session managers:
   - Only call `session_manager.run()` if Streamable HTTP is enabled
   - SSE transport doesn't require lifespan context

## Verification

```bash
uv run pytest tests/integration/test_mcp_streamable_http.py -k "compat" -v
# Expected: 5 passed
```

## Commit

```
feat(mcp): add configuration toggle for transport selection

Support SSE only, Streamable HTTP only, or both transports.
Enables gradual migration without breaking existing clients.
```