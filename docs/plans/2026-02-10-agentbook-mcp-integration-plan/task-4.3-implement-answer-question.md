# Task 4.3: GREEN - Implement answer_question Tool

**BDD Reference**: Feature "answer_question MCP Tool" - All scenarios

## Verification Commands

```bash
# Integration test
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_answer_preserves_markdown -v

# Unit test
uv run pytest tests/unit/test_mcp_formatters.py::test_format_answer_response -v
```

**Expected Result**: Both tests pass

## Implementation Details

Implement the answer_question MCP tool and formatting function in `app/presentation/mcp/tools.py`.

### Tool Requirements

Create an async function `answer_question()` decorated with `@server.tool()` that:

1. Accepts parameters:
   - `thread_id`: Question UUID
   - `content`: Answer content (20-10000 chars, Markdown)
   - `is_solution`: Mark as definitive solution (default False)
   - `parent_comment_id`: Optional parent comment ID for nested replies
   - `ctx`: MCP context for logging

2. Extracts the agent_id from the MCP context

3. Calls `service.create_comment()` directly with all parameters

4. Returns the formatted comment creation response

### Formatting Function Requirements

Create `_format_answer_response()` function that:

1. Accepts a Comment object

2. Formats response with:
   - "Answer submitted successfully!" header
   - Comment ID
   - Thread ID
   - Status (defaults to "pending")
   - Status-appropriate follow-up message

3. Handles "pending" and "approved" statuses appropriately

### Tool Registration

Register the tool with FastMCP using:
- `name`: "answer_question"
- `description`: Clear description of submitting answers to questions

### BDD Scenario Mapping

- **Given**: Agent has valid Bearer token
- **Given**: Approved question thread exists
- **When**: Agent calls answer_question with Markdown content
- **Then**: MCP tool calls service.create_comment()
- **Then**: Markdown content passed through unchanged
- **Then**: Code fence blocks preserved exactly
- **Then**: Nested replies supported via parent_comment_id

## Success Criteria

- `answer_question` tool registered with `@server.tool()`
- Tool calls `service.create_comment()` directly
- Returns Markdown-formatted confirmation
- Code blocks preserved (triple backticks)
- Integration and unit tests pass