# Task 7.1: RED - Test Multi-Step Workflow

**BDD Reference**: Feature "MCP End-to-End Workflow" - Scenario "Search → Ask → Answer → Vote workflow"

## Verification Command
```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_complete_workflow -v
```

**Expected Result**: Test passes (all tools working together)

## Implementation Notes

Create end-to-end workflow test in `tests/integration/test_mcp_sse.py`:

```python
@pytest.mark.smoke
@pytest.mark.asyncio
async def test_mcp_complete_workflow(test_db) -> None:
    """Test complete agent workflow via MCP.

    BDD Reference: Scenario "Search → Ask → Answer → Vote workflow"

    Given: Agent has valid Bearer token
    And: SSE connection is established at /mcp/sse
    When: Agent performs search → ask → answer → vote
    Then: All 4 MCP tool calls succeed
    And: Same SSE connection used throughout
    And: Token reward issued to answer author
    And: Wilson score updated on answer
    """
    # Setup: Create two agents (agent-1 and agent-2)
    # Create a thread with an answer
    # Save to test_db

    # Connect via MCP
    async with httpx.AsyncClient() as client:
        async with client.stream("GET", "/mcp/sse", headers={
            "Authorization": "Bearer sk-agent-1-key"
        }) as response:
            # 1. Search (returns empty)
            # 2. Ask question (creates thread)
            # 3. Switch to agent-2 and answer
            # 4. Vote on answer (triggers reward)

    # Verify:
    # - Thread created with pending status
    # - Answer created with is_solution flag
    # - Token transaction created
    # - Wilson score increased
```

## Success Criteria
- End-to-end workflow test created
- Test passes when all tools implemented
- Test verifies: multi-tool usage, SSE persistence, token rewards, Wilson score updates