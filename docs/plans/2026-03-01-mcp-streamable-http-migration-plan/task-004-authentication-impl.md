# Task 004: Authentication Integration Implementation

**Type**: impl
**Depends-on**: task-004-authentication-test

## Objective

Integrate authentication with Streamable HTTP transport to pass all tests.

## BDD Scenario

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
```

## Files to Modify

- `app/presentation/mcp/streamable_router.py`

## Implementation Steps

1. Import `get_verifier` from `app.presentation.mcp.auth`

2. In `mcp_endpoint` handler:
   - Extract `Authorization` header
   - Extract `X-API-Key` header
   - Call `verifier.verify(authorization, x_api_key)`
   - Store agent in `_mcp_server._agent`

3. Handle authentication failures:
   - Catch exceptions from `verifier.verify()`
   - Return HTTP 401 with appropriate error message

4. Ensure agent is available to tool handlers:
   - Tool handlers access `_mcp_server._agent`

## Code Structure

```python
async def mcp_endpoint(request: Request):
    verifier = get_verifier(request)
    authorization = request.headers.get("Authorization")
    x_api_key = request.headers.get("X-API-Key")

    try:
        if authorization or x_api_key:
            agent = verifier.verify(authorization=authorization, x_api_key=x_api_key)
            _mcp_server._agent = agent
        else:
            _mcp_server._agent = None
    except Exception:
        _mcp_server._agent = None
```

## Verification

```bash
uv run pytest tests/integration/test_mcp_streamable_http.py -k "authentication" -v
# Expected: 5 passed
```

## Commit

```
feat(mcp): integrate authentication with streamable http transport

Extract and verify authentication on each request before delegating to MCP.
```