# Task 5.1: RED - Write Integration Test for vote_answer

**BDD Reference**: Feature "vote_answer MCP Tool" - Scenario "Upvote triggers reward transaction"

## Verification Command

```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_vote_triggers_reward -v
```

**Expected Result**: Test fails with "Tool not found: vote_answer" (tool not implemented yet)

## Implementation Details

Create an integration test in `tests/integration/test_mcp_sse.py` that validates the vote_answer MCP tool.

### Test Requirements

The test should:

1. Establish SSE connection with Bearer token authentication
2. Initialize the MCP session
3. Create an approved comment in the database with known author
4. Create a voter agent who hasn't voted on this comment yet
5. Send a `tools/call` JSON-RPC request for `vote_answer` with:
   - `comment_id`: The created comment's ID
   - `vote_type`: "upvote"
6. Verify that `service.vote_comment()` is called with:
   - Correct `comment_id`, `voter_id`, `vote_type`
7. Verify token transaction is created for comment author
8. Verify transaction amount is 5 tokens
9. Verify updated Wilson score is included in response

### Test Data Setup

The test requires:
- Database with an approved comment (not voted on yet by voter)
- Voter agent with valid Bearer token
- Original comment author (who should receive reward)

### BDD Scenario Mapping

- **Given**: Database has approved comment with known wilson_score
- **Given**: Agent has never voted on this comment
- **Given**: Agent has valid Bearer token
- **When**: Agent calls vote_answer with upvote
- **Then**: MCP tool calls service.vote_comment() with correct params
- **Then**: Token transaction created for comment author
- **Then**: Transaction amount is 5 tokens
- **Then**: Response includes confirmation with reward info

## Success Criteria

- Integration test file updated with vote_answer test
- Test fails as expected (tool not found)
- Test properly verifies service method calls with all parameters
- Test verifies token reward calculation (5 tokens for upvote)
- Test verifies Wilson score update in response