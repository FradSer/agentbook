# Task 3.2: RED - Write Unit Test for Question Response Formatting

**BDD Reference**: Feature "ask_question MCP Tool" - Scenario "Successful question posting triggers moderation"

## Verification Command
```bash
uv run pytest tests/unit/test_mcp_formatters.py::test_format_question_response -v
```

**Expected Result**: Test fails with "ModuleNotFoundError" (formatting function not implemented yet)

## Implementation Notes

Create test in `tests/unit/test_mcp_formatters.py`:

```python
def test_format_question_response() -> None:
    """Test Markdown formatting of question response.

    BDD Reference: Scenario "Successful question posting triggers moderation"
    """
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
    assert "reviewed by" in result.lower() or "check back" in result.lower()


def test_format_question_response_approved() -> None:
    """Test formatting when question is immediately approved."""
    from app.domain.models import Thread
    from datetime import datetime
    from uuid import uuid4

    thread = Thread(
        thread_id=uuid4(),
        author_id=uuid4(),
        title="Approved question",
        body="Test body",
        tags=["test"],
        review_status="approved",
        created_at=datetime.utcnow(),
    )

    result = _format_question_response(thread)

    assert "Question posted successfully!" in result
    assert "Status: approved" in result
    assert "Your question is live!" in result
```

## Success Criteria
- Unit test file updated
- Test fails as expected (function not found)
- Test covers: pending status, approved status
- Test verifies Markdown formatting is correct