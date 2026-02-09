# Task 4.1: [RED] Write integration test for answer_question

**Type**: Test (RED)
**BDD Reference**: Scenario "Submit answer with code blocks via MCP"
**Estimated Time**: 45 minutes

## Objective

Write integration test for `answer_question` MCP tool that verifies Markdown code block preservation.

## Files to Modify

- `tests/integration/test_mcp_sse.py`

## Implementation Steps

Add test function:
```python
@pytest.mark.smoke
@pytest.mark.asyncio
async def test_mcp_answer_preserves_markdown(
    test_api_client: AsyncClient,
    test_db
):
    """
    Test answer_question tool preserves Markdown code blocks.

    BDD Reference: Scenario "Submit answer with code blocks via MCP"

    Given: Database has approved question "thread-3"
          And agent has valid API key "sk-abc"
    When: Agent sends answer_question with code blocks
    Then: MCP tool calls service.create_comment
          And code blocks are preserved exactly
          And comment is created successfully
    """
    # Arrange: Create test thread first
    from app.domain.models import Thread, Agent
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
        author_id=agent.agent_id,
        title="How to use SQLAlchemy async?",
        body="Need help with async engine",
        tags=["python", "sqlalchemy"],
        error_log=None,
        environment=None,
        embedding=None,
        created_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        review_status="approved",
        review_score=8.0
    )
    # Save to DB...

    # Prepare answer with code blocks
    answer_content = """Use async engine:

```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine("postgresql+asyncpg://...")
async with engine.begin() as conn:
    await conn.execute(text("SELECT 1"))
```

This enables async operations."""

    headers = {
        "X-API-Key": "sk-test-valid-key",
        "Accept": "text/event-stream"
    }

    mcp_request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "answer_question",
            "arguments": {
                "thread_id": str(thread.thread_id),
                "content": answer_content,
                "is_solution": True
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
                if data.get("id") == 4 and "result" in data:
                    result = data["result"]
                    break

        # Assert
        assert result is not None
        text = result["content"][0]["text"]
        assert "Answer submitted successfully" in text
        assert "Comment ID:" in text

        # Verify comment in database
        from app.infrastructure.persistence.sqlalchemy_repositories import (
            SQLAlchemyCommentRepository
        )
        repo = SQLAlchemyCommentRepository(test_db)

        # Extract comment ID
        import re
        comment_id_match = re.search(r"Comment ID: ([0-9a-f-]{36})", text)
        comment_id = comment_id_match.group(1)

        comment = await repo.get_by_id(comment_id)
        assert comment is not None
        assert comment.is_solution is True
        # Verify code blocks preserved
        assert "```python" in comment.content
        assert "create_async_engine" in comment.content
        assert "```" in comment.content
```

## Verification

Run test (should FAIL with "Tool not found: answer_question"):
```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_answer_preserves_markdown -v
```

**Expected Output**:
```
FAILED - MCP error: Tool not found: answer_question
```

## Success Criteria

- Test creates approved thread as prerequisite
- Test verifies comment creation via service
- Test checks database for comment with code blocks
- Code fence preservation verified (triple backticks)
- Test fails with expected error

## BDD Acceptance Criteria Mapping

From `bdd-specs.md`:
- ✅ Markdown content passed through unchanged to service
- ✅ Code fence blocks preserved (triple backticks)
- ✅ Comment record created with is_solution=true

## Next Task

Task 4.2: Write unit test for answer formatting
