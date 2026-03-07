# Task 005: Backward Compatibility Test

**Type**: test
**Depends-on**: task-004-authentication-impl

## Objective

Write tests for backward compatibility between SSE and Streamable HTTP transports.

## BDD Scenarios

```gherkin
Scenario: Legacy SSE endpoint remains functional
  When client sends GET request to /mcp/sse with Authorization: Bearer sk-valid-key
  Then SSE connection is established
  And existing v1 tools work: search_agentbook, ask_question, answer_question, vote_answer
  And response format matches existing SSE behavior

Scenario: New Streamable HTTP endpoint with v2 tools
  When client sends POST request to /mcp with Accept: application/json, text/event-stream
  Then Streamable HTTP session is established
  And v2 tools are available: resolve, contribute, report_outcome, get_context
  And response includes mcp-session-id header

Scenario: Client can use both transports simultaneously
  Given client has legacy SSE connection at /mcp/sse
  And client has Streamable HTTP session at /mcp
  When client calls tools on both connections
  Then both connections work independently
  And no state is shared between transports

Scenario: Configuration toggle between transports
  Given configuration setting MCP_TRANSPORT=streamable_http
  When server starts
  Then only Streamable HTTP endpoint is mounted
  And SSE endpoint returns 404
```

## Files to Modify

- `tests/integration/test_mcp_streamable_http.py`

## Test Cases

1. **test_legacy_sse_endpoint_functional** - SSE endpoint still works
2. **test_streamable_http_v2_tools** - New endpoint has v2 tools
3. **test_both_transports_simultaneously** - Both work independently
4. **test_config_streamable_http_only** - Config disables SSE
5. **test_config_sse_only** - Config disables Streamable HTTP

## Verification

```bash
uv run pytest tests/integration/test_mcp_streamable_http.py -k "compat" -v
# Expected: failed (RED phase)
```

## Commit

```
test(mcp): add backward compatibility tests

Test SSE legacy endpoint and transport configuration toggles.
```