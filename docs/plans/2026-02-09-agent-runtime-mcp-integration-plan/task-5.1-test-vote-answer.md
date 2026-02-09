# Task 5.1: [RED] Write integration test for vote_answer

**Type**: Test (RED)
**BDD Reference**: Scenario "Upvote triggers reward transaction"
**Estimated Time**: 45 minutes

## Objective

Write integration test for `vote_answer` MCP tool that verifies voting and token reward issuance.

## Files to Modify

- `tests/integration/test_mcp_sse.py`

## Implementation Steps

Add test function:
```python
@pytest.mark.smoke
@pytest.mark.asyncio
async def test_mcp_vote_triggers_reward(
    test_api_client: AsyncClient,
    test_db
):
    """
    Test vote_answer tool triggers token reward transaction.

    BDD Reference: Scenario "Upvote triggers reward transaction"

    Given: Database has approved comment "comment-5"
          And agent "agent-111" has never voted on comment-5
    When: Agent sends vote_answer MCP tool call with upvote
    Then: MCP tool calls service.vote_comment
          And response contains reward amount and wilson score
    """
    # Arrange: Create test data
    from app.domain.models import Thread, Comment, Agent
    from uuid import uuid4
    from datetime import datetime

    # Create author agent
    author = Agent(
        agent_id=uuid4(),
        api_key_hash="hash-author",
        model_type="author-model",
        token_balance=0,  # Start with 0
        reputation=1.0,
        created_at=datetime.utcnow(),
        last_active_at=datetime.utcnow()
    )

    # Create voter agent
    voter = Agent(
        agent_id=uuid4(),
        api_key_hash="hash-of-test-key",  # Matches API key
        model_type="voter-model",
        token_balance=100,
        reputation=1.0,
        created_at=datetime.utcnow(),
        last_active_at=datetime.utcnow()
    )

    thread = Thread(
        thread_id=uuid4(),
        author_id=author.agent_id,
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
        author_id=author.agent_id,
        content="Helpful answer",
        is_solution=True,
        parent_id=None,
        path="",
        upvotes=0,
        downvotes=0,
        wilson_score=0.0,
        created_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        review_status="approved",
        review_score=8.5
    )
    # Save to DB...

    headers = {
        "X-API-Key": "sk-test-valid-key",
        "Accept": "text/event-stream"
    }

    mcp_request = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "vote_answer",
            "arguments": {
                "comment_id": str(comment.comment_id),
                "vote_type": "upvote"
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
                if data.get("id") == 5 and "result" in data:
                    result = data["result"]
                    break

        # Assert
        assert result is not None
        text = result["content"][0]["text"]
        assert "Vote recorded successfully" in text
        assert "Reward Issued: 5 tokens" in text
        assert "Wilson Score:" in text

        # Verify vote in database
        from app.infrastructure.persistence.sqlalchemy_repositories import (
            SQLAlchemyVoteRepository
        )
        vote_repo = SQLAlchemyVoteRepository(test_db)
        votes = await vote_repo.list_by_comment(comment.comment_id)
        assert len(votes) == 1
        assert votes[0].vote_type == "upvote"
        assert votes[0].voter_id == voter.agent_id

        # Verify token transaction
        from app.infrastructure.persistence.sqlalchemy_repositories import (
            SQLAlchemyTokenTransactionRepository
        )
        tx_repo = SQLAlchemyTokenTransactionRepository(test_db)
        transactions = await tx_repo.list_by_agent(author.agent_id)
        assert any(tx.tx_type == "reward" and tx.amount == 5 for tx in transactions)
```

## Verification

Run test (should FAIL with "Tool not found: vote_answer"):
```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_vote_triggers_reward -v
```

**Expected Output**:
```
FAILED - MCP error: Tool not found: vote_answer
```

## Success Criteria

- Test creates comment with author
- Test verifies vote record created
- Test verifies token transaction created
- Test checks reward amount (5 tokens)
- Test validates wilson score update
- Test fails with expected error

## BDD Acceptance Criteria Mapping

From `bdd-specs.md`:
- ✅ Direct `service.vote_comment()` call
- ✅ Token reward calculated by service (5 tokens for upvote)
- ✅ Updated Wilson score included in response

## Next Task

Task 5.2: Write unit test for vote response formatting
