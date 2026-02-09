# Task 4.2: [RED] Write unit test for answer formatting

**Type**: Test (RED)
**BDD Reference**: Scenario "Submit answer with code blocks via MCP" - response format
**Estimated Time**: 20 minutes

## Objective

Write unit test for `_format_answer_response()` helper to verify comment creation response formatting.

## Files to Modify

- `tests/unit/test_mcp_formatters.py`

## Implementation Steps

Add test functions:
```python
def test_format_answer_response():
    """Test Markdown formatting of comment creation response."""
    from app.presentation.mcp.tools import _format_answer_response

    # Arrange: Mock comment object
    comment = {
        "comment_id": "660f9511-f3ac-52e5-b827-557766551111",
        "thread_id": "550e8400-e29b-41d4-a716-446655440000",
        "is_solution": True,
        "review_status": "pending",
        "created_at": "2026-02-07T15:00:00Z"
    }

    # Act
    result = _format_answer_response(comment)

    # Assert
    assert "Answer submitted successfully!" in result
    assert "Comment ID: 660f9511-f3ac-52e5-b827-557766551111" in result
    assert "Question ID: 550e8400-e29b-41d4-a716-446655440000" in result
    assert "Status: pending" in result
    assert "tokens" in result.lower() or "upvote" in result.lower()


def test_format_answer_response_not_solution():
    """Test formatting for regular comment (not marked as solution)."""
    from app.presentation.mcp.tools import _format_answer_response

    # Arrange
    comment = {
        "comment_id": "770f9511-f3ac-52e5-b827-557766551222",
        "thread_id": "880e8400-e29b-41d4-a716-446655440111",
        "is_solution": False,
        "review_status": "approved",
        "created_at": "2026-02-07T15:00:00Z"
    }

    # Act
    result = _format_answer_response(comment)

    # Assert
    assert "Answer submitted successfully!" in result
    assert "Comment ID:" in result
    # Should not indicate it's a solution
    # (optional: verify no "Solution" marker)
```

## Verification

Run test (should FAIL with AttributeError):
```bash
uv run pytest tests/unit/test_mcp_formatters.py::test_format_answer_response -v
```

**Expected Output**:
```
FAILED tests/unit/test_mcp_formatters.py::test_format_answer_response
AttributeError: module 'app.presentation.mcp.tools' has no attribute '_format_answer_response'
```

## Success Criteria

- Tests cover both solution and regular comment cases
- Assertions verify:
  - Success message
  - Comment ID
  - Thread ID reference
  - Review status
  - Helpful next steps (token earning)
- Test fails with expected error

## Test Isolation

✅ **No Service Calls**: Uses mock comment dict
✅ **No Database**: Pure function testing
✅ **No External Dependencies**: Isolated unit test

## Next Task

Task 4.3: Implement answer_question tool
