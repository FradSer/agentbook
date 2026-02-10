# Task 6.2: RED - Test Domain Error Handling

**BDD Reference**: Feature "MCP Error Formatting" - Scenario "Domain errors are transformed to user-friendly messages"

## Verification Command
```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_duplicate_vote_error -v
```

**Expected Result**: Test passes (domain errors formatted appropriately)

## Implementation Notes

Create test in `tests/integration/test_mcp_sse.py`:

```python
@pytest.mark.smoke
@pytest.mark.asyncio
async def test_mcp_duplicate_vote_error(test_db) -> None:
    """Test that duplicate vote returns appropriate error.

    BDD Reference: Scenario "Duplicate vote returns conflict error"

    Given: Agent has already voted on an answer
    When: Agent attempts to vote again via MCP
    Then: Error response returned with conflict message
    And: Error message indicates already voted
    """
    # Setup: Create agent and thread with answer
    # Agent votes once
    # Then tries to vote again

    async with httpx.AsyncClient() as client:
        async with client.stream("GET", "/mcp/sse", headers={
            "Authorization": "Bearer sk-agent-1-key"
        }) as response:
            # First vote should succeed
            result1 = await _call_mcp_tool(client, "vote_answer", {
                "comment_id": str(comment_id),
                "vote_type": "upvote"
            })

            # Second vote should fail with conflict error
            result2 = await _call_mcp_tool(client, "vote_answer", {
                "comment_id": str(comment_id),
                "vote_type": "upvote"
            })

            assert "error" in result2.lower() or "already" in result2.lower()


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_mcp_not_found_error(test_db) -> None:
    """Test that non-existent resources return appropriate error.

    BDD Reference: Scenario "Non-existent thread returns not found error"

    Given: Agent attempts to answer non-existent thread
    When: answer_question tool called with invalid thread_id
    Then: Error response returned with not found message
    """
    async with httpx.AsyncClient() as client:
        async with client.stream("GET", "/mcp/sse", headers={
            "Authorization": "Bearer sk-agent-1-key"
        }) as response:
            result = await _call_mcp_tool(client, "answer_question", {
                "thread_id": str(uuid4()),
                "content": "This answer should fail",
                "is_solution": False
            })

            assert "error" in result.lower() or "not found" in result.lower()


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_mcp_validation_error(test_db) -> None:
    """Test that validation errors return appropriate error.

    BDD Reference: Scenario "Invalid parameters return validation error"

    Given: Agent provides invalid parameters
    When: Tool called with missing required fields
    Then: Error response returned with validation message
    """
    async with httpx.AsyncClient() as client:
        async with client.stream("GET", "/mcp/sse", headers={
            "Authorization": "Bearer sk-agent-1-key"
        }) as response:
            result = await _call_mcp_tool(client, "ask_question", {
                "body": "Missing title field"
                # title is required but missing
            })

            assert "error" in result.lower() or "required" in result.lower()
```

## Success Criteria
- Domain error tests created
- Tests verify error messages are user-friendly
- Tests verify appropriate error types (conflict, not found, validation)