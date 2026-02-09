# Task 2.4: [RED] Test empty search results

**Type**: Test (RED)
**BDD Reference**: Scenario "Search with no results returns helpful message"
**Estimated Time**: 20 minutes

## Objective

Write integration test to verify graceful handling of empty search results (no matching questions).

## Files to Modify

- `tests/integration/test_mcp_sse.py`

## Implementation Steps

Add test function:
```python
@pytest.mark.smoke
@pytest.mark.asyncio
async def test_mcp_search_empty_results(
    test_api_client: AsyncClient,
    test_db  # Clean database
):
    """
    Test search_agentbook returns helpful message when no results found.

    BDD Reference: Scenario "Search with no results returns helpful message"

    Given: Database has NO questions matching "nonexistent-xyz-12345"
    When: Agent calls search_agentbook with that query
    Then: MCP tool returns TextContent: "No matching questions found."
    """
    # Arrange
    headers = {
        "X-API-Key": "sk-test-valid-key",
        "Accept": "text/event-stream"
    }

    mcp_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "search_agentbook",
            "arguments": {
                "query": "nonexistent-xyz-12345-no-match",
                "limit": 5
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
                if data.get("id") == 2 and "result" in data:
                    result = data["result"]
                    break

        # Assert
        assert result is not None
        assert "content" in result
        text = result["content"][0]["text"]
        assert "No matching questions found" in text
        # Should NOT contain error markers
        assert "❌" not in text
        assert "Error" not in text
```

## Verification

Run test (should PASS if Task 2.3 implemented correctly):
```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_search_empty_results -v
```

**Expected Output**:
```
tests/integration/test_mcp_sse.py::test_mcp_search_empty_results PASSED [100%]
```

## Success Criteria

- Test verifies empty result handling
- Message is user-friendly (not an error)
- No false error markers (❌, "Error")
- Test passes when formatter handles empty list correctly

## BDD Acceptance Criteria Verification

From `bdd-specs.md` Scenario "Search with no results returns helpful message":
- ✅ Empty service response handled gracefully
- ✅ Simple, clear message (not a technical error)

## Edge Cases Covered

- Empty database (no threads at all)
- Non-matching query (threads exist but don't match)
- Service returns `[]` successfully

## Next Steps

**Milestone 2 Complete!** Ready to commit:
```bash
git add app/presentation/mcp/tools.py tests/unit/test_mcp_formatters.py tests/integration/test_mcp_sse.py
git commit -m "feat(mcp): implement search_agentbook tool"
```

## Next Task

Task 3.1: Write integration test for ask_question
