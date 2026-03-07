# Task 001: Add MCP Transport Configuration

**Type**: config
**Depends-on**: none

## Objective

Add configuration settings to support MCP transport selection between SSE (legacy), Streamable HTTP (new), or both.

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

- `app/core/config.py` - Add MCP transport settings

## Implementation Steps

1. Add `mcp_transport` field to Settings class:
   - Type: `Literal["streamable_http", "sse", "both"]`
   - Default: `"both"` (for backward compatibility during migration)

2. Add `mcp_stateless` field:
   - Type: `bool`
   - Default: `True` (for horizontal scaling)

3. Add `mcp_json_response` field:
   - Type: `bool`
   - Default: `True` (for simpler responses)

4. Add `mcp_session_timeout` field (optional):
   - Type: `int`
   - Default: `3600` (1 hour)

## Verification

```bash
uv run python -c "from app.core.config import settings; print(settings.mcp_transport)"
# Expected: both
```

## Commit

```
feat(config): add mcp transport configuration settings

Add configuration options for MCP transport selection:
- mcp_transport: streamable_http | sse | both
- mcp_stateless: enable horizontal scaling
- mcp_json_response: JSON vs SSE response format
```