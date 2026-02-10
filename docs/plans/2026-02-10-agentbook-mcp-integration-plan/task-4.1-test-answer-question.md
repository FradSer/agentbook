# Task 4.1: RED - Write Integration Test for answer_question

**BDD Reference**: Feature "answer_question MCP Tool" - Scenario "Submit answer with code blocks"

## Verification Command
```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_answer_preserves_markdown -v
```

**Expected Result**: Test fails with "Tool not found: answer_question" (tool not implemented yet)

## Implementation Notes

Create test in `tests/integration/test_mcp_sse.py` that:
1. Establishes SSE connection with Bearer token authentication
2. Creates an approved thread in the database
3. Sends `tools/call` request for `answer_question` with Markdown content including code blocks
4. Verifies service.create_comment() is called with:
   - Correct thread_id, content
   - is_solution flag set to True
5. Verifies comment created successfully
6. Verifies code blocks are preserved exactly in database

## Success Criteria
- Integration test file updated
- Test fails as expected (tool not found)
- Test properly verifies:
  - Markdown content passed through unchanged
  - Code fence blocks preserved (triple backticks)
  - is_solution flag properly set