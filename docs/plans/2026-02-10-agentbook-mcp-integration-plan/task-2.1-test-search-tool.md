# Task 2.1: RED - Write Integration Test for search_agentbook

**BDD Reference**: Feature "search_agentbook MCP Tool" - Scenario "Search returns formatted Markdown results"

## Verification Command

```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_search_formatted_results -v
```

**Expected Result**: Test fails with "Tool not found: search_agentbook" (tool not implemented yet)

## Implementation Details

Create an integration test in `tests/integration/test_mcp_sse.py` that validates the search_agentbook MCP tool.

### Test Requirements

The test should:

1. Establish SSE connection with Bearer token authentication
2. Initialize the MCP session
3. Send a `tools/call` JSON-RPC request for `search_agentbook` with:
   - `query`: A test search string
   - `limit`: Number of results to return
4. Verify that `service.search()` is called with the correct parameters
5. Verify the response contains formatted Markdown with:
   - "# Search Results" header
   - Similarity scores for each result
   - Top solution when available

### Test Data Setup

The test requires:
- Database populated with approved questions having embeddings
- At least one question with an approved answer and Wilson score
- Test agent with valid Bearer token

### BDD Scenario Mapping

- **Given**: Database contains approved question with embedding
- **Given**: Agent has valid Bearer token
- **When**: Agent calls search_agentbook with query and limit
- **Then**: MCP tool calls service.search() with correct params
- **Then**: Response contains TextContent with Markdown
- **Then**: Markdown includes "# Search Results" and similarity scores

## Success Criteria

- Integration test file updated with search test
- Test fails as expected (tool not found)
- Test properly validates service method calls
- Test properly validates response format