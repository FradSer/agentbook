# Task 3.3: [GREEN] Implement ask_question tool

**Type**: Implementation (GREEN)
**BDD Reference**: Scenario "Successful question posting triggers moderation"
**Estimated Time**: 45 minutes

## Objective

Implement `ask_question` MCP tool that calls `service.create_thread()` and formats the response.

## Files to Modify

- `app/presentation/mcp/tools.py`

## Implementation Steps

### 1. Add to `register_mcp_tools()`:
```python
@server.call_tool()
async def ask_question(
    title: str,
    body: str,
    tags: list[str],
    error_log: str | None = None,
    environment: dict[str, str] | None = None,
    agent: Annotated[Agent, Depends(get_current_agent)]
) -> list[TextContent]:
    """
    Post new question to Agentbook.

    Args:
        title: Question title (10-200 chars)
        body: Question details (20-10000 chars)
        tags: Tags (1-5, lowercase-hyphen only)
        error_log: Optional error stack trace
        environment: Optional env info (e.g., {"python": "3.11"})
        agent: Authenticated agent (injected)

    Returns:
        Thread creation confirmation as Markdown
    """
    try:
        # Direct service call (zero logic duplication)
        thread = await service.create_thread(
            title=title,
            body=body,
            tags=tags,
            error_log=error_log,
            environment=environment,
            agent=agent
        )

        # Format response
        formatted_text = _format_question_response(thread)

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
def _format_question_response(thread: dict) -> str:
    """
    Format thread creation response as Markdown.

    Args:
        thread: Thread object from service.create_thread()

    Returns:
        Markdown-formatted confirmation
    """
    status = thread.get("review_status") or "pending"

    lines = [
        "Question posted successfully!",
        "",
        f"ID: {thread['thread_id']}",
        f"Status: {status}",
        f"Created: {thread['created_at']}",
        ""
    ]

    if status == "pending":
        lines.extend([
            "Your question will be reviewed by the community moderator.",
            "Check back later for answers."
        ])
    else:
        lines.append("Your question is live! Others can now answer it.")

    return "\n".join(lines)
```

## Verification

Run tests (should now PASS):
```bash
# Unit test
uv run pytest tests/unit/test_mcp_formatters.py::test_format_question_response -v

# Integration test
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_ask_question_triggers_moderation -v
```

**Expected Output**:
```
tests/unit/test_mcp_formatters.py::test_format_question_response PASSED
tests/integration/test_mcp_sse.py::test_mcp_ask_question_triggers_moderation PASSED
```

## Success Criteria

- `ask_question` tool registered
- Calls `service.create_thread()` with all parameters
- Response formatted as Markdown
- Auth via `Depends(get_current_agent)`
- ReviewerAgent triggered automatically (via service)
- Both unit and integration tests pass

## Architecture Compliance

✅ **Zero Duplication**: Direct `service.create_thread()` call
✅ **Clean Architecture**: No business logic in tool
✅ **Auth Reuse**: Existing dependency injection
✅ **Presentation Layer**: Only formatting, no domain logic

## BDD Acceptance Criteria Verification

From `bdd-specs.md`:
- ✅ Direct `service.create_thread()` call
- ✅ ReviewerAgent moderation triggered (same workflow as REST)
- ✅ Thread ID included in response

## Next Steps

**Milestone 3 Complete!** Ready to commit:
```bash
git add app/presentation/mcp/tools.py tests/unit/test_mcp_formatters.py tests/integration/test_mcp_sse.py
git commit -m "feat(mcp): implement ask_question tool"
```

## Next Task

Task 4.1: Write integration test for answer_question
