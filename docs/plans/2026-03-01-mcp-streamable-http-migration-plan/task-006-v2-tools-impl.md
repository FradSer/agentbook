# Task 006: V2 Tools Over Streamable HTTP Implementation

**Type**: impl
**Depends-on**: task-006-v2-tools-test

## Objective

Ensure v2 tools work correctly over Streamable HTTP transport with authenticated agent context.

## BDD Scenario

```gherkin
Scenario: resolve tool returns solutions
  Given knowledge base has solution S001 for "ImportError: pydantic.v1"
  When agent calls resolve tool with:
    | parameter    | value                                      |
    | description  | ImportError: cannot import 'pydantic.v1'   |
    | error_signature | ImportError                            |
    | environment  | {"python": "3.12", "pydantic": "2.5.0"}    |
    | auto_post    | true                                       |
  Then service.resolve() is called with agent_id from authenticated agent
  And response contains solutions with confidence scores
```

## Files to Verify

- `app/presentation/mcp/tools_v2.py` - Verify tool handlers use `_mcp_server._agent`
- `app/presentation/mcp/streamable_router.py` - Verify agent is set before tool calls

## Implementation Steps

1. Verify `tools_v2.py` has `_get_authenticated_agent(server)` helper:
   - Extract agent from `server._agent`
   - Raise error if not authenticated

2. Verify each tool handler:
   - `handle_resolve` uses agent from `_get_authenticated_agent`
   - `handle_contribute` uses agent for author_id
   - `handle_report_outcome` uses agent for reporter_id
   - `handle_get_context` passes agent context

3. Ensure tool response formatting:
   - Results formatted as JSON-RPC responses
   - Error responses use proper JSON-RPC error codes

## Verification

```bash
uv run pytest tests/integration/test_mcp_streamable_http.py -k "tool" -v
# Expected: 5 passed
```

## Commit

```
feat(mcp): ensure v2 tools work with streamable http transport

Verify tool handlers extract authenticated agent from server context.
```