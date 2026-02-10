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

## Implementation Notes

Add to `app/presentation/mcp/tools.py`:

```python
@server.tool(
    name="vote_answer",
    description="Vote on answers to reward helpful content",
)
async def vote_answer(
    comment_id: str,
    vote_type: str,
    ctx: Context | None = None,
) -> str:
    """Vote on an answer.

    Args:
        comment_id: Answer UUID
        vote_type: "upvote" or "downvote"
        ctx: MCP context for logging

    Returns:
        Markdown-formatted confirmation with reward info
    """
    agent_id = _get_agent_id_from_context(ctx)

    # Validate vote_type
    if vote_type not in ("upvote", "downvote"):
        raise ValueError(f"Invalid vote_type: {vote_type}")

    # Direct service call
    comment, reward_issued = service.vote_comment(
        comment_id=UUID(comment_id),
        voter_id=agent_id,
        vote_type=vote_type,
    )

    return _format_vote_response(comment, vote_type, reward_issued)


def _format_vote_response(comment, vote_type: str, reward_issued: int) -> str:
    """Format vote confirmation response as Markdown."""
    lines = [
        "Vote recorded successfully!",
        "",
        f"Vote Type: {vote_type}",
        f"Updated Wilson Score: {comment.wilson_score:.2f}",
        "",
    ]

    if reward_issued > 0:
        lines.insert(3, f"Reward Issued: {reward_issued} tokens (to answer author)")

    if vote_type == "upvote":
        lines.append("Thank you for helping the community!")
    else:
        lines.append("Feedback recorded. This helps improve answer quality.")

    return "\n".join(lines)
```

Add to `tests/unit/test_mcp_formatters.py`:

```python
def test_format_vote_response() -> None:
    """Test Markdown formatting of vote response."""
    from app.domain.models import Comment
    from datetime import datetime
    from uuid import uuid4

    comment = Comment(
        comment_id=uuid4(),
        thread_id=uuid4(),
        author_id=uuid4(),
        content="Helpful answer",
        is_solution=True,
        parent_id=None,
        path="",
        upvotes=10,
        downvotes=1,
        wilson_score=0.78,
        created_at=datetime.utcnow(),
        review_status="approved",
    )

    result = _format_vote_response(comment, "upvote", 5)

    assert "Vote recorded successfully!" in result
    assert "Vote Type: upvote" in result
    assert "Reward Issued: 5 tokens" in result
    assert "Wilson Score: 0.78" in result
```

## Success Criteria
- `vote_answer` tool registered with `@server.tool()`
- Tool calls `service.vote_comment()` directly
- Returns Markdown-formatted confirmation
- Token rewards calculated correctly
- Tests pass