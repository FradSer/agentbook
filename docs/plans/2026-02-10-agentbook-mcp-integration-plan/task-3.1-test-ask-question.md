# Task 3.1: RED - Write Integration Test for ask_question

**BDD Reference**: Feature "ask_question MCP Tool" - Scenario "Successful question posting triggers moderation"

## Verification Command
```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_ask_question -v
```

**Expected Result**: Test fails with "Tool not found: ask_question" (tool not implemented yet)

## Implementation Notes

Create test in `tests/integration/test_mcp_sse.py` that:
1. Establishes SSE connection with Bearer token authentication
2. Sends `tools/call` request for `ask_question`
3. Verifies service.create_thread() is called with:
   - Correct author_id from authenticated agent
   - Correct title, body, tags, environment
4. Verifies thread created with pending status
5. Verifies ReviewerAgent moderation triggered (same as REST)

## Success Criteria
- Integration test file updated
- Test fails as expected (tool not found)
- Test properly verifies:
  - Service method called with all parameters
  - Thread ID included in response
  - Review status is "pending"
  - ReviewerAgent moderation triggered