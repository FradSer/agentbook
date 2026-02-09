# Task 3.2: [RED] Write unit test for question response formatting

**Type**: Test (RED)
**BDD Reference**: Scenario "Successful question posting triggers moderation" - response format
**Estimated Time**: 20 minutes

## Objective

Write unit test for `_format_question_response()` helper to verify Markdown formatting of thread creation response.

## Files to Modify

- `tests/unit/test_mcp_formatters.py`

## Implementation Steps

Add test functions:
```python
def test_format_question_response():
    """Test Markdown formatting of thread creation response."""
    from app.presentation.mcp.tools import _format_question_response
    from uuid import uuid4
    from datetime import datetime

    # Arrange: Mock thread object
    thread = {
        "thread_id": "550e8400-e29b-41d4-a716-446655440000",
        "title": "How to configure Redis?",
        "review_status": "pending",
        "created_at": "2026-02-07T14:30:00Z"
    }

    # Act
    result = _format_question_response(thread)

    # Assert
    assert "Question posted successfully!" in result
    assert "ID: 550e8400-e29b-41d4-a716-446655440000" in result
    assert "Status: pending" in result
    assert "reviewed by" in result.lower() or "check back" in result.lower()


def test_format_question_response_approved():
    """Test formatting when question is immediately approved."""
    from app.presentation.mcp.tools import _format_question_response

    # Arrange: Mock approved thread
    thread = {
        "thread_id": "660f9511-f3ac-52e5-b827-557766551111",
        "title": "Approved question",
        "review_status": "approved",
        "created_at": "2026-02-07T14:30:00Z"
    }

    # Act
    result = _format_question_response(thread)

    # Assert
    assert "Question posted successfully!" in result
    assert "Status: approved" in result
```

## Verification

Run test (should FAIL with ModuleNotFoundError or AttributeError):
```bash
uv run pytest tests/unit/test_mcp_formatters.py::test_format_question_response -v
```

**Expected Output**:
```
FAILED tests/unit/test_mcp_formatters.py::test_format_question_response
AttributeError: module 'app.presentation.mcp.tools' has no attribute '_format_question_response'
```

## Success Criteria

- Test covers pending status (most common)
- Test covers approved status (edge case)
- Assertions verify all required fields:
  - Success message
  - Thread ID (UUID format)
  - Status
  - Helpful next steps message
- Test fails with expected error

## Test Isolation

✅ **No Service Calls**: Uses mock thread dict
✅ **No Database**: Pure function testing
✅ **No External Dependencies**: Isolated unit test

## Next Task

Task 3.3: Implement ask_question tool (will make tests pass)
