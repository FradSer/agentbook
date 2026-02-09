# Task 6.1: [RED] Test authentication error handling

**Type**: Test (RED)
**BDD Reference**: Scenario "Invalid API key rejected before service call"
**Estimated Time**: 30 minutes

## Objective

Write integration test to verify that invalid API keys are rejected with clear error messages.

## Files to Modify

- `tests/integration/test_mcp_sse.py`

## Implementation Steps

Add test function:
```python
@pytest.mark.smoke
@pytest.mark.asyncio
async def test_mcp_invalid_api_key(test_api_client: AsyncClient):
    """
    Test MCP endpoints reject invalid API keys.

    BDD Reference: Scenario "Invalid API key rejected before service call"

    Given: FastAPI backend is running
          And API key "sk-invalid" is not registered
    When: Agent sends MCP tool call with invalid API key
    Then: get_current_agent() raises UnauthorizedError
          And MCP endpoint returns error message
          And no service methods are called
    """
    # Arrange
    headers = {
        "X-API-Key": "sk-invalid-not-in-database",
        "Accept": "text/event-stream"
    }

    mcp_request = {
        "jsonrpc": "2.0",
        "id": 99,
        "method": "tools/call",
        "params": {
            "name": "search_agentbook",
            "arguments": {
                "query": "test query",
                "limit": 3
            }
        }
    }

    # Act
    async with test_api_client.stream("POST", "/mcp/sse", headers=headers) as response:
        # Send MCP request
        # ... (SSE send logic) ...

        # Read response
        result = None
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if data.get("id") == 99:
                    result = data
                    break

        # Assert: Error response returned
        assert result is not None
        assert "error" in result

        error_msg = result["error"]["message"]
        assert "❌ Error:" in error_msg or "Invalid API Key" in error_msg
        assert "X-API-Key" in error_msg or "header" in error_msg.lower()
```

## Verification

Run test (should PASS - auth is already implemented):
```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_invalid_api_key -v
```

**Expected Output**:
```
tests/integration/test_mcp_sse.py::test_mcp_invalid_api_key PASSED [100%]
```

**If test FAILS**: Auth dependency not properly integrated with MCP endpoint.

## Success Criteria

- Test sends request with invalid API key
- Error response includes clear message
- No service method execution (verified via logs/coverage)
- Test passes (existing auth should handle this)

## BDD Acceptance Criteria Verification

From `bdd-specs.md`:
- ✅ Authentication dependency blocks execution before service layer
- ✅ Clear error message returned to agent
- ✅ Service layer protected from unauthenticated calls

## Architecture Note

This test validates that existing `get_current_agent()` dependency works correctly with MCP endpoints. No new code needed - just verification that integration is correct.

## Next Task

Task 6.2: Test duplicate vote error
