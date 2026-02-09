# Task 5.2: [RED] Write unit test for vote response formatting

**Type**: Test (RED)
**BDD Reference**: Scenario "Upvote triggers reward transaction" - response format
**Estimated Time**: 20 minutes

## Objective

Write unit test for `_format_vote_response()` helper to verify vote confirmation formatting.

## Files to Modify

- `tests/unit/test_mcp_formatters.py`

## Implementation Steps

Add test functions:
```python
def test_format_vote_response_upvote():
    """Test Markdown formatting of upvote response with reward."""
    from app.presentation.mcp.tools import _format_vote_response

    # Arrange: Mock vote response
    vote_data = {
        "vote_type": "upvote",
        "comment": {
            "comment_id": "660f9511-f3ac-52e5-b827-557766551111",
            "wilson_score": 0.78
        },
        "reward_issued": 5
    }

    # Act
    result = _format_vote_response(vote_data)

    # Assert
    assert "Vote recorded successfully!" in result
    assert "Vote Type: upvote" in result
    assert "Reward Issued: 5 tokens" in result
    assert "Wilson Score: 0.78" in result
    assert "community" in result.lower() or "thank" in result.lower()


def test_format_vote_response_downvote():
    """Test formatting of downvote (no reward)."""
    from app.presentation.mcp.tools import _format_vote_response

    # Arrange
    vote_data = {
        "vote_type": "downvote",
        "comment": {
            "comment_id": "770f9511-f3ac-52e5-b827-557766551222",
            "wilson_score": 0.45
        },
        "reward_issued": 0  # No reward for downvotes
    }

    # Act
    result = _format_vote_response(vote_data)

    # Assert
    assert "Vote recorded successfully!" in result
    assert "Vote Type: downvote" in result
    assert "Wilson Score: 0.45" in result
    # Should NOT mention reward for downvotes
    assert "Reward Issued: 0" not in result or "no reward" in result.lower()


def test_format_vote_response_no_reward():
    """Test formatting when vote doesn't trigger reward (edge case)."""
    from app.presentation.mcp.tools import _format_vote_response

    # Arrange: Upvote but no reward (e.g., voting on own answer)
    vote_data = {
        "vote_type": "upvote",
        "comment": {
            "comment_id": "880f9511-f3ac-52e5-b827-557766551333",
            "wilson_score": 0.50
        },
        "reward_issued": 0
    }

    # Act
    result = _format_vote_response(vote_data)

    # Assert
    assert "Vote recorded successfully!" in result
    assert "Wilson Score: 0.50" in result
```

## Verification

Run test (should FAIL with AttributeError):
```bash
uv run pytest tests/unit/test_mcp_formatters.py::test_format_vote_response_upvote -v
```

**Expected Output**:
```
FAILED tests/unit/test_mcp_formatters.py::test_format_vote_response_upvote
AttributeError: module 'app.presentation.mcp.tools' has no attribute '_format_vote_response'
```

## Success Criteria

- Tests cover upvote with reward (common case)
- Tests cover downvote (no reward)
- Tests cover edge case (upvote but no reward)
- Assertions verify:
  - Success message
  - Vote type
  - Reward amount (when applicable)
  - Wilson score
  - Helpful message
- Test fails with expected error

## Test Isolation

✅ **No Service Calls**: Uses mock vote data
✅ **No Database**: Pure function testing
✅ **No External Dependencies**: Isolated unit test

## Next Task

Task 5.3: Implement vote_answer tool
