# Task 002: Implement MCP Authentication

**Area**: Backend
**Priority**: Critical
**BDD Scenario**: MCP tool call with valid API key (ref: Scenario 3), MCP tool uses authenticated agent for writes (ref: Scenario 4)

## Objective

Enforce authentication on MCP SSE endpoint and pass authenticated agent to tools.

## Files to Modify

- `app/presentation/mcp/router.py`
- `app/presentation/mcp/tools.py`
- `app/presentation/mcp/auth.py`

## What to Implement

### 1. Update API Key Prefix (auth.py)

Change `api_key_prefix` default from `"sk-agentbook-"` to `"ak_"` to match config.

### 2. Enforce Auth on SSE Endpoint (router.py)

- Remove the placeholder agent creation
- Add authentication check in `handle_sse()`:
  - Extract agent from `request.state.mcp_agent` (set by middleware)
  - Return 401 if no authenticated agent
  - Store agent in server context for tool access

### 3. Update Tools to Use Authenticated Agent (tools.py)

- Create a helper function `_get_authenticated_agent(server)` that:
  - Retrieves agent from server context
  - Raises error if no agent found
- Update all tool functions to use `_get_authenticated_agent()` instead of `server._agent`
- Remove unused `_format_error()` function (dead code)
- Remove unused `hash_api_key` import from auth.py

## Verification

```bash
uv run pytest tests/unit/presentation/mcp/test_auth.py -v
```

Expected: All tests **PASS** (Green phase).

## Dependencies

**task-001-mcp-auth-tests.md** - Tests must exist first

## BDD References

- Scenario 3: MCP tool call with valid API key
- Scenario 4: MCP tool uses authenticated agent for writes