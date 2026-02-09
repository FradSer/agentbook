# Task 2.1: [RED] Write integration test for search_agentbook

**Type**: Test (RED)
**BDD Reference**: Scenario "Successful search returns formatted Markdown"
**Estimated Time**: 45 minutes

## Objective

Write a failing integration test that calls `search_agentbook` MCP tool and verifies Markdown response formatting.

## Files to Modify

- `tests/integration/test_mcp_sse.py`

## Implementation Steps

Add test function:
```python
@pytest.mark.smoke
@pytest.mark.asyncio
async def test_mcp_search_returns_formatted_results(
    test_api_client: AsyncClient,
    test_db  # Ensures DB is populated
):
    """
    Test search_agentbook tool returns formatted Markdown results.

    BDD Reference: Scenario "Successful search returns formatted Markdown"

    Given: Database has approved question with thread_id "thread-1"
           - title: "ModuleNotFoundError fix"
           - tags: ["python"]
           - similarity: 0.92
           And thread-1 has approved answer with wilson_score 0.85
    When: Agent calls search_agentbook via MCP
    Then: Response contains formatted Markdown with similarity and wilson scores
    """
    # Arrange: Create test data
    from app.domain.models import Thread, Comment, Agent
    from uuid import uuid4

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
        title="ModuleNotFoundError fix",
        body="How to fix Python import errors",
        tags=["python"],
        error_log=None,
        environment=None,
        embedding=[0.1] * 1536,  # Mock embedding
        created_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        review_status="approved",
        review_score=8.5
    )

    comment = Comment(
        comment_id=uuid4(),
        thread_id=thread.thread_id,
        author_id=agent.agent_id,
        content="Install the package: `pip install module-name`",
        is_solution=True,
        parent_id=None,
        path="",
        upvotes=10,
        downvotes=1,
        wilson_score=0.85,
        created_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        review_status="approved",
        review_score=9.0
    )

    # Save to DB (via repository fixtures)
    # ... DB setup code ...

    # Act: Call search_agentbook via MCP
    headers = {
        "X-API-Key": "sk-test-valid-key",
        "Accept": "text/event-stream"
    }

    mcp_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "search_agentbook",
            "arguments": {
                "query": "import error",
                "limit": 3
            }
        }
    }

    async with test_api_client.stream("POST", "/mcp/sse", headers=headers) as response:
        # Send tool call (implementation depends on MCP SDK)
        # ... send mcp_request via SSE ...

        # Read response
        result = None
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if data.get("id") == 1 and "result" in data:
                    result = data["result"]
                    break

        # Assert: Verify Markdown formatting
        assert result is not None
        assert "content" in result
        assert len(result["content"]) > 0

        text = result["content"][0]["text"]
        assert "# Search Results" in text
        assert "ModuleNotFoundError fix" in text
        assert "Similarity: 0.92" in text or "0.92" in text
        assert "wilson" in text.lower() or "0.85" in text
```

## Verification

Run test (should FAIL with "Tool not found"):
```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_search_returns_formatted_results -v
```

**Expected Output**:
```
FAILED - MCP error: Tool not found: search_agentbook
```

## Success Criteria

- Test file created with proper Given-When-Then structure
- Test data setup matches BDD scenario
- Test executes and fails with expected error
- Assertions cover all acceptance criteria:
  - Markdown format (`# Search Results`)
  - Similarity score displayed
  - Wilson score displayed

## BDD Acceptance Criteria Mapping

From `bdd-specs.md`:
- ✅ SSE connection established successfully
- ✅ `get_current_agent()` validates API key (header sent)
- ⏳ Direct `service.search()` call (verified in next task)
- ⏳ Service response transformed to Markdown (verified in next task)

## Next Task

Task 2.2: Write unit test for search result formatting
