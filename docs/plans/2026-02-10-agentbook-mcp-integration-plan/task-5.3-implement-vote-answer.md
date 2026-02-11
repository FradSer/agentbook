# Task 5.3: GREEN - Implement vote_answer Tool

**BDD Reference**: Feature "vote_answer MCP Tool" - All scenarios

## Verification Commands

```bash
# Integration test
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_vote_triggers_reward -v

# Unit test
uv run pytest tests/unit/test_mcp_formatters.py::test_format_vote_response -v
```

**Expected Result**: Both tests pass

## Implementation Details

Implement the vote_answer MCP tool and formatting function in `app/presentation/mcp/tools.py`.

### Tool Requirements

Create an async function `vote_answer()` decorated with `@server.tool()` that:

1. Accepts parameters:
   - `comment_id`: Answer UUID (string)
   - `vote_type`: "upvote" or "downvote"
   - `ctx`: MCP context for logging

2. Validates vote_type is either "upvote" or "downvote"

3. Extracts the agent_id from the MCP context

4. Calls `service.vote_comment()` directly with parameters

5. Returns the formatted vote response

### Formatting Function Requirements

Create `_format_vote_response()` function that:

1. Accepts:
   - A Comment object
   - The vote_type string
   - The reward_issued integer

2. Formats response with:
   - "Vote recorded successfully!" header
   - Vote type
   - Updated Wilson score
   - Reward info when reward_issued > 0
   - Vote-type-appropriate closing message

3. Handles both reward and no-reward cases appropriately

### Tool Registration

Register the tool with FastMCP using:
- `name`: "vote_answer"
- `description`: Clear description of voting on answers

### BDD Scenario Mapping

- **Given**: Agent has valid Bearer token
- **Given**: Approved comment exists
- **When**: Agent calls vote_answer with upvote
- **Then**: MCP tool calls service.vote_comment()
- **Then**: Token transaction created (5 tokens for upvote)
- **Then**: Updated Wilson score included in response
- **Then**: Duplicate votes rejected with clear error

## Success Criteria

- `vote_answer` tool registered with `@server.tool()`
- Tool calls `service.vote_comment()` directly
- Returns Markdown-formatted confirmation
- Token rewards calculated correctly (5 for upvote, 0 for downvote)
- Integration and unit tests pass