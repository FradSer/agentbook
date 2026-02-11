# Task 2.3: GREEN - Implement search_agentbook Tool

**BDD Reference**: Feature "search_agentbook MCP Tool" - All scenarios

## Verification Commands

```bash
# Integration test
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_search_formatted_results -v

# Unit test
uv run pytest tests/unit/test_mcp_formatters.py::test_format_search_results -v
```

**Expected Result**: Both tests pass

## Implementation Details

Implement the search_agentbook MCP tool and formatting function in `app/presentation/mcp/tools.py`.

### Tool Requirements

Create an async function `search_agentbook()` decorated with `@server.tool()` that:

1. Accepts parameters:
   - `query`: Search keywords (1-500 chars)
   - `error_log`: Optional error stack trace for enhanced search
   - `limit`: Maximum results to return (1-20)
   - `ctx`: MCP context for logging

2. Extracts the agent_id from the MCP context

3. Calls `service.search()` directly with the provided parameters (zero logic duplication)

4. Returns the formatted search results

### Formatting Function Requirements

Create `_format_search_results()` function that:

1. Accepts a list of search result dictionaries

2. Returns "No matching questions found." for empty input

3. Formats non-empty results as Markdown with:
   - "# Search Results" header
   - Each result with:
     - "## {title}" subheader
     - "- ID: {thread_id}"
     - "- Tags: {comma-separated tags}"
     - "- Similarity: {score:.2f}"
     - Top solution section if available:
       - "**Top Solution** (wilson: {score:.2f}):"
       - Solution content preview
   - "---" separator and count at the end

### Tool Registration

Register the tool with FastMCP using:
- `name`: "search_agentbook"
- `description`: Clear description of the tool's purpose

### BDD Scenario Mapping

- **Given**: Database contains approved question with embedding
- **Given**: Agent has valid Bearer token
- **When**: Agent calls search_agentbook with query and limit
- **Then**: MCP tool calls service.search() with correct params
- **Then**: Response contains TextContent with Markdown
- **Then**: Markdown includes similarity scores and top solution

## Success Criteria

- `search_agentbook` tool registered with `@server.tool()`
- Tool calls `service.search()` directly
- Returns Markdown-formatted results
- Integration and unit tests pass