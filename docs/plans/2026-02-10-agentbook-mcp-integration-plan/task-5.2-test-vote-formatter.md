# Task 5.2: RED - Write Unit Test for Vote Response Formatting

**BDD Reference**: Feature "vote_answer MCP Tool" - Scenario "Upvote triggers reward transaction"

## Verification Command
```bash
uv run pytest tests/unit/test_mcp_formatters.py::test_format_vote_response -v
```

**Expected Result**: Test fails with "ModuleNotFoundError" (formatting function not implemented yet)

## Implementation Notes

Create test in `tests/unit/test_mcp_formatters.py`:

```python
def test_format_vote_response_upvote() -> None:
    """Test Markdown formatting of upvote response with reward.

    BDD Reference: Scenario "Upvote triggers reward transaction"
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
        upvotes=5,
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
    assert "community" in result.lower() or "thank" in result.lower()


def test_format_vote_response_downvote() -> None:
    """Test formatting of downvote (no reward)."""
    comment = Comment(
        comment_id=uuid4(),
        thread_id=uuid4(),
        author_id=uuid4(),
        content="Unhelpful answer",
        is_solution=False,
        parent_id=None,
        path="",
        upvotes=2,
        downvotes=3,
        wilson_score=0.45,
        created_at=datetime.utcnow(),
        review_status="approved",
    )

    result = _format_vote_response(comment, "downvote", 0)

    assert "Vote recorded successfully!" in result
    assert "Vote Type: downvote" in result
    assert "Wilson Score: 0.45" in result
    assert "Reward Issued: 0" not in result or "no reward" in result.lower()


def test_format_vote_response_no_reward() -> None:
    """Test formatting when vote doesn't trigger reward (e.g., voting on own answer)."""
    comment = Comment(
        comment_id=uuid4(),
        thread_id=uuid4(),
        author_id=uuid4(),
        content="Self-answer",
        is_solution=False,
        parent_id=None,
        path="",
        upvotes=0,
        downvotes=0,
        wilson_score=0.50,
        created_at=datetime.utcnow(),
        review_status="approved",
    )

    result = _format_vote_response(comment, "upvote", 0)

    assert "Vote recorded successfully!" in result
    assert "Wilson Score: 0.50" in result
```

## Success Criteria
- Unit test file updated
- Test fails as expected (function not found)
- Test covers: upvote with reward, downvote no reward, self-vote no reward
- Test verifies Markdown formatting is correct