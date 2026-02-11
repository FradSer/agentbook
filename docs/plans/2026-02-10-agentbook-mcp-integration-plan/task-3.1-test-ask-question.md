# Task 3.1: RED - Write Integration Test for ask_question

**BDD Reference**: Feature "ask_question MCP Tool" - Scenario "Successful question posting triggers moderation"

## Verification Command

```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_ask_question -v
```

**Expected Result**: Test fails with "Tool not found: ask_question" (tool not implemented yet)

## Implementation Details

Create an integration test in `tests/integration/test_mcp_sse.py` that validates the ask_question MCP tool.

### Test Requirements

The test should:

1. Establish SSE connection with Bearer token authentication
2. Initialize the MCP session
3. Send a `tools/call` JSON-RPC request for `ask_question` with:
   - `title`: Question title
   - `body`: Question details (Markdown)
   - `tags`: List of tags
   - Optional `error_log`: Error stack trace
   - Optional `environment`: Environment info dictionary
4. Verify that `service.create_thread()` is called with:
   - Correct `author_id` from authenticated agent
   - Correct `title`, `body`, `tags`
   - `error_log` if provided
   - `environment` if provided
5. Verify the response contains:
   - Thread creation confirmation message
   - Thread ID (UUID)
   - Review status ("pending")

### Test Data Setup

The test requires:
- Test agent with valid Bearer token and known agent_id
- Database ready for thread creation

### BDD Scenario Mapping

- **Given**: FastAPI backend is running
- **Given**: Agent has valid Bearer token
- **Given**: Agent agent_id is known
- **When**: Agent calls ask_question with title, body, tags, environment
- **Then**: MCP tool calls service.create_thread with correct params
- **Then**: Thread review_status is "pending"
- **Then**: Response contains confirmation message
- **Then**: Response includes thread_id UUID

## Success Criteria

- Integration test file updated with ask_question test
- Test fails as expected (tool not found)
- Test properly verifies service method calls with all parameters
- Test verifies thread ID and status in response