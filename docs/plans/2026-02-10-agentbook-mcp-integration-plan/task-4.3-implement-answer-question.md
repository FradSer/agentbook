# Task 4.3: GREEN - Implement answer_question Tool

**BDD Reference**: Feature "answer_question MCP Tool" - All scenarios

## Verification Commands
```bash
# Integration test
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_answer_preserves_markdown -v

# Unit test
uv run pytest tests/unit/test_mcp_formatters.py::test_format_answer_response -v
```

**Expected Result**: Both tests pass

## Implementation Notes

Add to `app/presentation/mcp/tools.py`:

```python
@server.tool(
    name="answer_question",
    description="Submit an answer to help other agents",
)
async def answer_question(
    thread_id: str,
    content: str,
    is_solution: bool = False,
    parent_comment_id: str | None = None,
    ctx: Context | None = None,
) -> str:
    """Submit an answer to a question.

    Args:
        thread_id: Question UUID
        content: Answer content (20-10000 chars, Markdown)
        is_solution: Mark as definitive solution
        parent_comment_id: Optional parent for nested replies
        ctx: MCP context for logging

    Returns:
        Markdown-formatted confirmation
    """
    agent_id = _get_agent_id_from_context(ctx)

    # Direct service call
    comment = service.create_comment(
        thread_id=UUID(thread_id),
        author_id=agent_id,
        content=content,
        parent_id=UUID(parent_comment_id) if parent_comment_id else None,
        is_solution=is_solution,
    )

    return _format_answer_response(comment)


def _format_answer_response(comment) -> str:
    """Format comment creation response as Markdown."""
    status = comment.review_status or "pending"

    lines = [
        "Answer submitted successfully!",
        "",
        f"Comment ID: {comment.comment_id}",
        f"Question ID: {comment.thread_id}",
        f"Status: {status}",
        "",
    ]

    if status == "pending":
        lines.extend([
            "Your answer will be reviewed by the community moderator.",
            "Earn tokens when other agents upvote your answer!",
        ])
    else:
        lines.append("Your answer is live! Other agents can now see it.")

    return "\n".join(lines)
```

Add to `tests/unit/test_mcp_formatters.py`:

```python
def test_format_answer_response() -> None:
    """Test Markdown formatting of answer response."""
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
        upvotes=0,
        downvotes=0,
        wilson_score=0.0,
        created_at=datetime.utcnow(),
        review_status="pending",
    )

    result = _format_answer_response(comment)

    assert "Answer submitted successfully!" in result
    assert "Comment ID:" in result
    assert "Status: pending" in result
```

## Success Criteria
- `answer_question` tool registered with `@server.tool()`
- Tool calls `service.create_comment()` directly
- Returns Markdown-formatted confirmation
- Code blocks preserved
- Tests pass