# Task 6.1: RED - Test Authentication Error Handling

**BDD Reference**: Feature "MCP Authentication" - Scenario "Missing Bearer token returns 401 error"

## Verification Command
```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_auth_required -v
```

**Expected Result**: Test passes (FastMCP's built-in auth handles missing tokens)

## Implementation Notes

Create test in `tests/integration/test_mcp_sse.py`:

```python
@pytest.mark.smoke
@pytest.mark.asyncio
async def test_mcp_auth_required(test_db) -> None:
    """Test that missing Bearer token returns authentication error.

    BDD Reference: Scenario "Missing Bearer token returns 401 error"

    Given: Agent attempts to connect without Bearer token
    When: SSE connection request sent to /mcp/sse
    Then: Connection is rejected with 401 status
    And: Error message indicates authentication required
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/mcp/sse",
            headers={},  # No Authorization header
            timeout=5.0
        )

        assert response.status_code == 401
        assert "authentication" in response.text.lower() or "unauthorized" in response.text.lower()


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_mcp_invalid_token(test_db) -> None:
    """Test that invalid Bearer token is rejected.

    BDD Reference: Scenario "Invalid API key returns 401 error"

    Given: Agent provides invalid Bearer token
    When: SSE connection request sent to /mcp/sse
    Then: Connection is rejected with 401 status
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/mcp/sse",
            headers={
                "Authorization": "Bearer sk-invalid-key"
            },
            timeout=5.0
        )

        assert response.status_code == 401
```

## Success Criteria
- Authentication error tests created
- Tests verify 401 status for missing/invalid tokens
- Tests verify user-friendly error messages