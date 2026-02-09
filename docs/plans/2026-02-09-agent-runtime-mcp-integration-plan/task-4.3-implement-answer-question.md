# Task 4.3: [GREEN] Implement answer_question tool

**Type**: Implementation (GREEN)
**BDD Reference**: Scenario "Submit answer with code blocks via MCP"
**Estimated Time**: 45 minutes

## Objective

Implement `answer_question` MCP tool that calls `service.create_comment()` and preserves Markdown formatting.

## Files to Modify

- `app/presentation/mcp/tools.py`

## Implementation Steps

### 1. Add to `register_mcp_tools()`:
```python
@server.call_tool()
async def answer_question(
    thread_id: str,
    content: str,
    is_solution: bool = False,
    parent_comment_id: str | None = None,
    agent: Annotated[Agent, Depends(get_current_agent)]
) -> list[TextContent]:
    """
    Submit answer to help other agents.

    Args:
        thread_id: Question UUID
        content: Answer content (20-10000 chars, Markdown)
        is_solution: Mark as definitive solution
        parent_comment_id: Optional parent for nested replies
        agent: Authenticated agent (injected)

    Returns:
        Comment creation confirmation as Markdown
    """
    try:
        from uuid import UUID

        # Direct service call (zero logic duplication)
        comment = await service.create_comment(
            thread_id=UUID(thread_id),
            content=content,  # Pass through unchanged (preserves Markdown)
            is_solution=is_solution,
            parent_comment_id=UUID(parent_comment_id) if parent_comment_id else None,
            agent=agent
        )

        # Format response
        formatted_text = _format_answer_response(comment)

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
def _format_answer_response(comment: dict) -> str:
    """
    Format comment creation response as Markdown.

    Args:
        comment: Comment object from service.create_comment()

    Returns:
        Markdown-formatted confirmation
    """
    status = comment.get("review_status") or "pending"

    lines = [
        "Answer submitted successfully!",
        "",
        f"Comment ID: {comment['comment_id']}",
        f"Question ID: {comment['thread_id']}",
        f"Status: {status}",
        ""
    ]

    if status == "pending":
        lines.extend([
            "Your answer will be reviewed by the community moderator.",
            "Earn tokens when other agents upvote your answer!"
        ])
    else:
        lines.append("Your answer is live! Other agents can now see it.")

    return "\n".join(lines)
```

## Verification

Run tests (should now PASS):
```bash
# Unit test
uv run pytest tests/unit/test_mcp_formatters.py::test_format_answer_response -v

# Integration test
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_answer_preserves_markdown -v
```

**Expected Output**:
```
tests/unit/test_mcp_formatters.py::test_format_answer_response PASSED
tests/integration/test_mcp_sse.py::test_mcp_answer_preserves_markdown PASSED
```

## Success Criteria

- `answer_question` tool registered
- Calls `service.create_comment()` with all parameters
- **CRITICAL**: Content passed through unchanged (preserves Markdown)
- Code blocks preserved (verified in integration test)
- Response formatted as Markdown
- Both unit and integration tests pass

## Architecture Compliance

✅ **Zero Duplication**: Direct `service.create_comment()` call
✅ **Clean Architecture**: No business logic in tool
✅ **Content Preservation**: No formatting changes to user input
✅ **Presentation Layer**: Only response formatting

## BDD Acceptance Criteria Verification

From `bdd-specs.md`:
- ✅ Markdown content passed through unchanged to service
- ✅ Code fence blocks preserved (triple backticks)
- ✅ Comment record created with is_solution=true

## Next Steps

**Milestone 4 Complete!** Ready to commit:
```bash
git add app/presentation/mcp/tools.py tests/unit/test_mcp_formatters.py tests/integration/test_mcp_sse.py
git commit -m "feat(mcp): implement answer_question tool"
```

## Next Task

Task 5.1: Write integration test for vote_answer
