# Task 4.2: RED - Write Unit Test for Answer Formatting

**BDD Reference**: Feature "answer_question MCP Tool" - Scenario "Submit answer with code blocks"

## Verification Command
```bash
uv run pytest tests/unit/test_mcp_formatters.py::test_format_answer_response -v
```

**Expected Result**: Test fails with "ModuleNotFoundError" (formatting function not implemented yet)

## Implementation Notes

Create test in `tests/unit/test_mcp_formatters.py`:

```python
def test_format_answer_response() -> None:
    """Test Markdown formatting of answer response.

    BDD Reference: Scenario "Submit answer with code blocks"
    """
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
    assert "tokens" in result.lower() or "upvote" in result.lower()


def test_format_answer_response_not_solution() -> None:
    """Test formatting for regular comment (not marked as solution)."""
    from app.domain.models import Comment
    from datetime import datetime
    from uuid import uuid4

    comment = Comment(
        comment_id=uuid4(),
        thread_id=uuid4(),
        author_id=uuid4(),
        content="Regular comment",
        is_solution=False,
        parent_id=None,
        path="",
        upvotes=0,
        downvotes=0,
        wilson_score=0.0,
        created_at=datetime.utcnow(),
        review_status="approved",
    )

    result = _format_answer_response(comment)

    assert "Answer submitted successfully!" in result
    assert "Comment ID:" in result
    assert "Status: approved" in result
```

## Success Criteria
- Unit test file updated
- Test fails as expected (function not found)
- Test covers: solution flag, non-solution comment
- Test verifies Markdown formatting is correct