# Task 3.1: [RED] Write integration test for ask_question

**Type**: Test (RED)
**BDD Reference**: Scenario "Successful question posting triggers moderation"
**Estimated Time**: 45 minutes

## Objective

Write integration test for `ask_question` MCP tool that verifies thread creation and ReviewerAgent notification.

## Files to Modify

- `tests/integration/test_mcp_sse.py`

## Implementation Steps

Add test function:
```python
@pytest.mark.smoke
@pytest.mark.asyncio
async def test_mcp_ask_question_triggers_moderation(
    test_api_client: AsyncClient,
    test_db
):
    """
    Test ask_question tool creates thread and triggers ReviewerAgent.

    BDD Reference: Scenario "Successful question posting triggers moderation"

    Given: FastAPI backend is running
          And agent has valid API key "sk-agent-456"
    When: Agent sends ask_question MCP tool call
    Then: MCP tool calls service.create_thread with correct parameters
          And ReviewerAgent is notified (same as REST API)
          And response contains thread ID and status "pending"
    """
    # Arrange
    headers = {
        "X-API-Key": "sk-test-valid-key",
        "Accept": "text/event-stream"
    }

    mcp_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "ask_question",
            "arguments": {
                "title": "How to configure Redis timeout?",
                "body": "Getting connection timeout errors when connecting to Redis from FastAPI. How can I increase the timeout?",
                "tags": ["fastapi", "redis"],
                "environment": {"python": "3.11", "redis": "7.0"}
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
                if data.get("id") == 3 and "result" in data:
                    result = data["result"]
                    break

        # Assert
        assert result is not None
        assert "content" in result
        text = result["content"][0]["text"]

        # Verify response format
        assert "Question posted successfully" in text
        assert "ID:" in text
        assert "Status: pending" in text

        # Extract thread ID from response
        import re
        thread_id_match = re.search(r"ID: ([0-9a-f-]{36})", text)
        assert thread_id_match is not None
        thread_id = thread_id_match.group(1)

        # Verify thread created in database
        from app.infrastructure.persistence.sqlalchemy_repositories import (
            SQLAlchemyThreadRepository
        )
        repo = SQLAlchemyThreadRepository(test_db)
        thread = await repo.get_by_id(thread_id)

        assert thread is not None
        assert thread.title == "How to configure Redis timeout?"
        assert thread.review_status == "pending"
        assert "fastapi" in thread.tags
        assert "redis" in thread.tags
        assert thread.environment == {"python": "3.11", "redis": "7.0"}
```

## Verification

Run test (should FAIL with "Tool not found: ask_question"):
```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_ask_question_triggers_moderation -v
```

**Expected Output**:
```
FAILED - MCP error: Tool not found: ask_question
```

## Success Criteria

- Test verifies thread creation via service
- Test checks database for created thread
- Test validates response format (ID, status)
- Test confirms pending review status
- Test fails with expected error (tool not found)

## BDD Acceptance Criteria Mapping

From `bdd-specs.md`:
- ✅ Direct `service.create_thread()` call
- ✅ ReviewerAgent moderation triggered (via pending status)
- ✅ Thread ID included in response

## Next Task

Task 3.2: Write unit test for question response formatting
