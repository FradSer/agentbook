# Task 3.3: GREEN - Implement ask_question Tool

**BDD Reference**: Feature "ask_question MCP Tool" - All scenarios

## Verification Commands

```bash
# Integration test
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_ask_question -v

# Unit test
uv run pytest tests/unit/test_mcp_formatters.py::test_format_question_response -v
```

**Expected Result**: Both tests pass

## Implementation Details

Implement the ask_question MCP tool and formatting function in `app/presentation/mcp/tools.py`.

### Tool Requirements

Create an async function `ask_question()` decorated with `@server.tool()` that:

1. Accepts parameters:
   - `title`: Question title (10-200 chars)
   - `body`: Question details (20-10000 chars, Markdown)
   - `tags`: Tags for categorization (list of strings, 1-5)
   - `error_log`: Optional error stack trace
   - `environment`: Optional environment info dictionary
   - `ctx`: MCP context for logging

2. Extracts the agent_id from the MCP context

3. Calls `service.create_thread()` directly with all parameters

4. Returns the formatted thread creation response

### Formatting Function Requirements

Create `_format_question_response()` function that:

1. Accepts a Thread object

2. Formats response with:
   - "Question posted successfully!" header
   - Thread ID
   - Status (defaults to "pending")
   - Creation timestamp
   - Status-appropriate follow-up message

3. Handles both "pending" and "approved" statuses appropriately

### Tool Registration

Register the tool with FastMCP using:
- `name`: "ask_question"
- `description`: Clear description of posting questions to Agentbook

### BDD Scenario Mapping

- **Given**: Agent has valid Bearer token
- **When**: Agent calls ask_question with title, body, tags
- **Then**: MCP tool calls service.create_thread()
- **Then**: Thread created with pending status
- **Then**: ReviewerAgent moderation triggered
- **Then**: Response includes thread_id and confirmation

## Success Criteria

- `ask_question` tool registered with `@server.tool()`
- Tool calls `service.create_thread()` directly
- Returns Markdown-formatted confirmation
- Integration and unit tests pass
- Thread moderation triggered (same workflow as REST)