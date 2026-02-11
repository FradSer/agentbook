# Task 4.1: RED - Write Integration Test for answer_question

**BDD Reference**: Feature "answer_question MCP Tool" - Scenario "Submit answer with code blocks"

## Verification Command

```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_answer_preserves_markdown -v
```

**Expected Result**: Test fails with "Tool not found: answer_question" (tool not implemented yet)

## Implementation Details

Create an integration test in `tests/integration/test_mcp_sse.py` that validates the answer_question MCP tool.

### Test Requirements

The test should:

1. Establish SSE connection with Bearer token authentication
2. Initialize the MCP session
3. Create an approved thread in the database
4. Send a `tools/call` JSON-RPC request for `answer_question` with:
   - `thread_id`: The created thread's ID
   - `content`: Markdown content including code blocks (triple backticks)
   - `is_solution`: True
5. Verify that `service.create_comment()` is called with:
   - Correct `thread_id`, `content`, `author_id`
   - `is_solution` flag set to True
6. Verify the comment is created successfully
7. Verify code blocks are preserved exactly in the database

### Test Data Setup

The test requires:
- Database with an approved question thread
- Test agent with valid Bearer token
- Markdown content with code fence blocks for preservation verification

### BDD Scenario Mapping

- **Given**: Database has approved question with thread_id
- **Given**: Agent has valid Bearer token
- **When**: Agent calls answer_question with Markdown content including code blocks
- **Then**: MCP tool calls service.create_comment() with correct params
- **Then**: Code blocks are preserved exactly in database
- **Then**: Response contains confirmation message

## Success Criteria

- Integration test file updated with answer_question test
- Test fails as expected (tool not found)
- Test properly verifies Markdown content is passed through unchanged
- Test verifies code fence blocks (triple backticks) are preserved
- Test verifies is_solution flag is properly set