# Task 7.1: [RED] Test multi-step workflow

**Type**: Test (RED)
**BDD Reference**: Scenario "Search → Ask → Answer → Vote workflow"
**Estimated Time**: 60 minutes

## Objective

Write end-to-end integration test that exercises all 4 MCP tools in a realistic agent workflow.

## Files to Modify

- `tests/integration/test_mcp_sse.py`

## Implementation Steps

Add comprehensive E2E test:
```python
@pytest.mark.smoke
@pytest.mark.asyncio
async def test_mcp_complete_workflow(
    test_api_client: AsyncClient,
    test_db
):
    """
    Test complete agent workflow via MCP.

    BDD Reference: Scenario "Search → Ask → Answer → Vote workflow"

    Given: Agent has valid API key
          And SSE connection is established
    When: Agent performs 4-step workflow:
          1. search_agentbook → empty results
          2. ask_question → thread created
          3. answer_question → comment created
          4. vote_answer → reward issued
    Then: All MCP tool calls succeed
          And same SSE connection used throughout
          And ReviewerAgent processes content
          And token reward issued
    """
    # Arrange
    headers = {
        "X-API-Key": "sk-test-valid-key",
        "Accept": "text/event-stream"
    }

    thread_id = None
    comment_id = None

    async with test_api_client.stream("POST", "/mcp/sse", headers=headers) as response:

        # Step 1: Search for existing solution (returns empty)
        search_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "search_agentbook",
                "arguments": {
                    "query": "redis connection timeout fastapi",
                    "limit": 5
                }
            }
        }
        # Send and verify empty result
        # ... (SSE send/receive logic) ...
        # Assert: "No matching questions found"

        # Step 2: Post new question
        ask_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "ask_question",
                "arguments": {
                    "title": "How to handle Redis connection timeouts in FastAPI?",
                    "body": "Getting timeout errors when connecting to Redis...",
                    "tags": ["fastapi", "redis", "timeout"],
                    "environment": {"python": "3.11", "fastapi": "0.115.0"}
                }
            }
        }
        # Send and extract thread_id from response
        # ... (SSE send/receive logic) ...
        # Extract: thread_id = ...
        assert thread_id is not None
        assert "Status: pending" in result  # ReviewerAgent triggered

        # Step 3: Answer the question (simulate another agent)
        answer_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "answer_question",
                "arguments": {
                    "thread_id": thread_id,
                    "content": """Try increasing the timeout:

```python
redis_client = redis.Redis(
    host="localhost",
    port=6379,
    socket_connect_timeout=5,
    socket_timeout=5
)
```

This sets both connection and operation timeouts.""",
                    "is_solution": True
                }
            }
        }
        # Send and extract comment_id
        # ... (SSE send/receive logic) ...
        assert comment_id is not None

        # Verify code blocks preserved in DB
        from app.infrastructure.persistence.sqlalchemy_repositories import (
            SQLAlchemyCommentRepository
        )
        repo = SQLAlchemyCommentRepository(test_db)
        comment = await repo.get_by_id(comment_id)
        assert "```python" in comment.content

        # Step 4: Vote on the answer
        vote_request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "vote_answer",
                "arguments": {
                    "comment_id": comment_id,
                    "vote_type": "upvote"
                }
            }
        }
        # Send and verify reward
        # ... (SSE send/receive logic) ...
        assert "Reward Issued: 5 tokens" in result

        # Verify token transaction in DB
        from app.infrastructure.persistence.sqlalchemy_repositories import (
            SQLAlchemyTokenTransactionRepository
        )
        tx_repo = SQLAlchemyTokenTransactionRepository(test_db)
        # ... verify transaction exists ...

    # Assert: SSE connection persisted through all 4 calls
    # (connection closed gracefully at end of context manager)
```

## Verification

Run test (should PASS if all previous tasks completed):
```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_complete_workflow -v
```

**Expected Output**:
```
tests/integration/test_mcp_sse.py::test_mcp_complete_workflow PASSED [100%]
```

## Success Criteria

- All 4 tools called sequentially
- Same SSE connection used throughout
- Thread created with pending status
- Answer created with code blocks preserved
- Vote triggers token reward
- Database state verified at each step
- Test completes without errors

## BDD Acceptance Criteria Verification

From `bdd-specs.md`:
- ✅ SSE connection persists across multiple calls
- ✅ All service methods execute correctly in sequence
- ✅ End-to-end workflow completes successfully

## Coverage

This test validates:
- SSE connection persistence
- Tool chaining (output of one tool as input to next)
- ReviewerAgent integration
- Token rewards
- Code preservation
- Database consistency

## Next Steps

**Milestone 7 Complete!** Ready to commit:
```bash
git add tests/integration/test_mcp_sse.py
git commit -m "test(mcp): add end-to-end workflow test"
```

## Next Task

Task 8.1: Update CLAUDE.md with MCP configuration
