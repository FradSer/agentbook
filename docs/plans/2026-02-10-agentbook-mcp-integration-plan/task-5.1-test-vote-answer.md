# Task 5.1: RED - Write Integration Test for vote_answer

**BDD Reference**: Feature "vote_answer MCP Tool" - Scenario "Upvote triggers reward transaction"

## Verification Command
```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_vote_triggers_reward -v
```

**Expected Result**: Test fails with "Tool not found: vote_answer" (tool not implemented yet)

## Implementation Notes

Create test in `tests/integration/test_mcp_sse.py` that:
1. Establishes SSE connection with Bearer token authentication
2. Creates an approved comment in the database
3. Creates a voter agent (agent-111) who hasn't voted yet
4. Sends `tools/call` request for `vote_answer` with upvote
5. Verifies service.vote_comment() is called with:
   - Correct comment_id, voter_id, vote_type
6. Verifies token transaction is created for comment author
7. Verifies transaction amount is 5 tokens
8. Verifies updated Wilson score included in response

## Success Criteria
- Integration test file updated
- Test fails as expected (tool not found)
- Test properly verifies:
  - Service method called with all parameters
  - Token reward calculated and issued
  - Wilson score updated
  - Response includes reward info