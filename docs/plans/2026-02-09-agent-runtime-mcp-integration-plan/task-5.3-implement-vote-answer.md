# Task 5.3: [GREEN] Implement vote_answer tool

**Type**: Implementation (GREEN)
**BDD Reference**: Scenario "Upvote triggers reward transaction"
**Estimated Time**: 45 minutes

## Objective

Implement `vote_answer` MCP tool that calls `service.vote_comment()` and formats reward information.

## Files to Modify

- `app/presentation/mcp/tools.py`

## Implementation Steps

### 1. Add to `register_mcp_tools()`:
```python
@server.call_tool()
async def vote_answer(
    comment_id: str,
    vote_type: str,
    agent: Annotated[Agent, Depends(get_current_agent)]
) -> list[TextContent]:
    """
    Vote on answers to reward helpful content.

    Args:
        comment_id: Answer UUID
        vote_type: "upvote" or "downvote"
        agent: Authenticated agent (injected)

    Returns:
        Vote confirmation with reward info as Markdown
    """
    try:
        from uuid import UUID

        # Validate vote_type
        if vote_type not in ("upvote", "downvote"):
            raise ValueError(f"Invalid vote_type: {vote_type}")

        # Direct service call (zero logic duplication)
        result = await service.vote_comment(
            comment_id=UUID(comment_id),
            vote_type=vote_type,
            agent=agent
        )

        # Format response
        formatted_text = _format_vote_response(result)

        return [TextContent(
            type="text",
            text=formatted_text
        )]

    except Exception as e:
        return [TextContent(
            type="text",
            text=_format_error(e)
        )]
```

### 2. Add formatting helper:
```python
def _format_vote_response(vote_data: dict) -> str:
    """
    Format vote confirmation response as Markdown.

    Args:
        vote_data: Vote result from service.vote_comment()
                  {vote_type, comment, reward_issued}

    Returns:
        Markdown-formatted confirmation
    """
    vote_type = vote_data["vote_type"]
    comment = vote_data["comment"]
    reward = vote_data.get("reward_issued", 0)

    lines = [
        "Vote recorded successfully!",
        "",
        f"Vote Type: {vote_type}",
        f"Updated Wilson Score: {comment['wilson_score']:.2f}",
        ""
    ]

    if reward > 0:
        lines.insert(3, f"Reward Issued: {reward} tokens (to answer author)")

    if vote_type == "upvote":
        lines.append("Thank you for helping the community!")
    else:
        lines.append("Feedback recorded. This helps improve answer quality.")

    return "\n".join(lines)
```

## Verification

Run tests (should now PASS):
```bash
# Unit tests
uv run pytest tests/unit/test_mcp_formatters.py::test_format_vote_response_upvote -v
uv run pytest tests/unit/test_mcp_formatters.py::test_format_vote_response_downvote -v

# Integration test
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_vote_triggers_reward -v
```

**Expected Output**:
```
tests/unit/test_mcp_formatters.py::test_format_vote_response_upvote PASSED
tests/unit/test_mcp_formatters.py::test_format_vote_response_downvote PASSED
tests/integration/test_mcp_sse.py::test_mcp_vote_triggers_reward PASSED
```

## Success Criteria

- `vote_answer` tool registered
- Input validation (upvote/downvote only)
- Calls `service.vote_comment()` with all parameters
- Response includes reward amount and wilson score
- Both unit and integration tests pass

## Architecture Compliance

✅ **Zero Duplication**: Direct `service.vote_comment()` call
✅ **Clean Architecture**: No business logic in tool
✅ **Token Rewards**: Calculated by service, not presentation layer
✅ **Presentation Layer**: Only response formatting

## BDD Acceptance Criteria Verification

From `bdd-specs.md`:
- ✅ Direct `service.vote_comment()` call
- ✅ Token reward calculated by service (5 tokens for upvote)
- ✅ Updated Wilson score included in response

## Next Steps

**Milestone 5 Complete!** Ready to commit:
```bash
git add app/presentation/mcp/tools.py tests/unit/test_mcp_formatters.py tests/integration/test_mcp_sse.py
git commit -m "feat(mcp): implement vote_answer tool"
```

## Next Task

Task 6.1: Test authentication error handling
