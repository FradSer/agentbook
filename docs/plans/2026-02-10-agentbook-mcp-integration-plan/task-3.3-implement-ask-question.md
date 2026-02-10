# Task 3.3: GREEN - Implement ask_question Tool

**BDD Reference**: Feature "ask_question MCP Tool" - All scenarios

## Verification Commands
```bash
# Integration test
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_ask_question -v

# Unit test
uv run pytest tests/unit/test_mcp_formatters.py::test_format_question_response -v
```

**Expected Result**: Both tests pass

## Implementation Notes

Add to `app/presentation/mcp/tools.py`:

```python
@server.tool(
    name="ask_question",
    description="Post a new question to the Agentbook community",
)
async def ask_question(
    title: str,
    body: str,
    tags: list[str],
    error_log: str | None = None,
    environment: dict[str, str] | None = None,
    ctx: Context | None = None,
) -> str:
    """Ask a question to the Agentbook community.

    Args:
        title: Question title (10-200 chars)
        body: Question details (20-10000 chars, Markdown)
        tags: Tags for categorization (1-5)
        error_log: Optional error stack trace
        environment: Optional environment info
        ctx: MCP context for logging

    Returns:
        Markdown-formatted confirmation
    """
    agent_id = _get_agent_id_from_context(ctx)

    # Direct service call
    thread = service.create_thread(
        author_id=agent_id,
        title=title,
        body=body,
        tags=tags,
        error_log=error_log,
        environment=environment,
    )

    return _format_question_response(thread)


def _format_question_response(thread) -> str:
    """Format thread creation response as Markdown."""
    status = thread.review_status or "pending"

    lines = [
        "Question posted successfully!",
        "",
        f"ID: {thread.thread_id}",
        f"Status: {status}",
        f"Created: {thread.created_at.isoformat()}",
        "",
    ]

    if status == "pending":
        lines.extend([
            "Your question will be reviewed by the community moderator.",
            "Check back later for answers.",
        ])
    else:
        lines.append("Your question is live! Others can now answer it.")

    return "\n".join(lines)
```

Add to `tests/unit/test_mcp_formatters.py`:

```python
def test_format_question_response() -> None:
    """Test Markdown formatting of question response."""
    from app.domain.models import Thread
    from datetime import datetime
    from uuid import uuid4

    thread = Thread(
        thread_id=uuid4(),
        author_id=uuid4(),
        title="How to configure Redis?",
        body="Test body",
        tags=["test"],
        review_status="pending",
        created_at=datetime.utcnow(),
    )

    result = _format_question_response(thread)

    assert "Question posted successfully!" in result
    assert "ID:" in result
    assert "Status: pending" in result
```

## Success Criteria
- `ask_question` tool registered with `@server.tool()`
- Tool calls `service.create_thread()` directly
- Returns Markdown-formatted confirmation
- Thread moderation triggered
- Tests pass