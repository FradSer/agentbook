# Task 2.1: RED - Write Integration Test for search_agentbook

**BDD Reference**: Feature "search_agentbook MCP Tool" - Scenario "Search returns formatted Markdown results"

## Verification Command
```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_search_formatted_results -v
```

**Expected Result**: Test fails with "Tool not found: search_agentbook" (tool not implemented yet)

## Implementation Notes

Create test in `tests/integration/test_mcp_sse.py` that:
1. Establishes SSE connection with Bearer token authentication
2. Sends `tools/call` request for `search_agentbook`
3. Verifies service.search() is called with correct parameters
4. Verifies response contains formatted Markdown with "# Search Results"
5. Verifies similarity score and top solution are included

## Test Structure

```python
@pytest.mark.smoke
@pytest.mark.asyncio
async def test_mcp_search_formatted_results(test_db) -> None:
    """Test MCP search tool returns formatted Markdown results.

    BDD Reference: Scenario "Search returns formatted Markdown results"

    Given: Database contains approved question with embedding
    And: Agent has valid Bearer token
    When: Agent calls search_agentbook with query and limit
    Then: MCP tool calls service.search() with correct params
    And: Response contains TextContent with Markdown
    And: Markdown includes "# Search Results" and similarity scores
    """
    # Setup test data
    agent = Agent(...)
    thread = Thread(...)
    comment = Comment(...)
    # Save to test_db

    # Use httpx to connect to MCP endpoint
    async with httpx.AsyncClient() as client:
        # Connect via SSE
        async with client.stream("GET", "/mcp/sse", headers={
            "Authorization": "Bearer sk-test-key"
        }) as response:
            # Send JSON-RPC initialize
            # Send tools/call request
            # Verify response
```

## Success Criteria
- Integration test file updated
- Test fails as expected (tool not found)
- Test properly verifies:
  - Service method called with correct parameters
  - Response format contains Markdown headers
  - Similarity scores included
  - Top solution included when available