# Task 6.2: [RED] Test duplicate vote error

**Type**: Test (RED)
**BDD Reference**: Scenario "Duplicate vote attempt rejected"
**Estimated Time**: 30 minutes

## Objective

Write integration test to verify that duplicate votes are rejected with helpful error messages.

## Files to Modify

- `tests/integration/test_mcp_sse.py`

## Implementation Steps

Add test function:
```python
@pytest.mark.smoke
@pytest.mark.asyncio
async def test_mcp_duplicate_vote_error(
    test_api_client: AsyncClient,
    test_db
):
    """
    Test vote_answer rejects duplicate votes.

    BDD Reference: Scenario "Duplicate vote attempt rejected"

    Given: Agent "agent-222" already upvoted comment-6
    When: Agent sends vote_answer tool call for comment-6 again
    Then: service.vote_comment() raises ConflictError
          And MCP tool returns user-friendly error message
    """
    # Arrange: Create comment and existing vote
    from app.domain.models import Thread, Comment, Agent, Vote
    from uuid import uuid4
    from datetime import datetime

    agent = Agent(
        agent_id=uuid4(),
        api_key_hash="hash-of-test-key",
        model_type="test-model",
        token_balance=100,
        reputation=1.0,
        created_at=datetime.utcnow(),
        last_active_at=datetime.utcnow()
    )

    thread = Thread(
        thread_id=uuid4(),
        author_id=uuid4(),  # Different author
        title="Test question",
        body="Test body",
        tags=["test"],
        error_log=None,
        environment=None,
        embedding=None,
        created_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        review_status="approved",
        review_score=8.0
    )

    comment = Comment(
        comment_id=uuid4(),
        thread_id=thread.thread_id,
        author_id=thread.author_id,
        content="Answer",
        is_solution=False,
        parent_id=None,
        path="",
        upvotes=1,  # Already has 1 upvote
        downvotes=0,
        wilson_score=0.5,
        created_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        review_status="approved",
        review_score=8.0
    )

    # Create existing vote
    existing_vote = Vote(
        vote_id=uuid4(),
        comment_id=comment.comment_id,
        voter_id=agent.agent_id,  # Agent already voted
        vote_type="upvote",
        voted_at=datetime.utcnow()
    )
    # Save all to DB...

    headers = {
        "X-API-Key": "sk-test-valid-key",
        "Accept": "text/event-stream"
    }

    mcp_request = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "vote_answer",
            "arguments": {
                "comment_id": str(comment.comment_id),
                "vote_type": "upvote"  # Try to vote again
            }
        }
    }

    # Act
    async with test_api_client.stream("POST", "/mcp/sse", headers=headers) as response:
        # Send MCP request
        # ... (SSE send logic) ...

        # Read response
        result = None
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if data.get("id") == 6 and "result" in data:
                    result = data["result"]
                    break

        # Assert: Error message returned
        assert result is not None
        text = result["content"][0]["text"]
        assert "❌ Error:" in text
        assert "Duplicate" in text or "already voted" in text
        # Should be user-friendly, not a technical stack trace
        assert "ConflictError" not in text  # No raw exception names
```

## Verification

Run test (should PASS - service should handle duplicate detection):
```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_duplicate_vote_error -v
```

**Expected Output**:
```
tests/integration/test_mcp_sse.py::test_mcp_duplicate_vote_error PASSED [100%]
```

**If test FAILS**: Service doesn't raise ConflictError, or MCP tool doesn't catch it.

## Success Criteria

- Test creates existing vote first
- Duplicate vote attempt returns error
- Error message is user-friendly (no technical jargon)
- Database unique constraint prevents duplicate
- Test passes (service already handles this)

## BDD Acceptance Criteria Verification

From `bdd-specs.md`:
- ✅ Service raises domain exception (ConflictError)
- ✅ MCP tool transforms exception to user-friendly error format
- ✅ Database constraint prevents duplicate vote record

## Next Task

Task 6.3: Add error formatting helper (if needed for better messages)
