# Task 1.1: [RED] Write integration test for SSE connection

**Type**: Test (RED)
**BDD Reference**: Feature "MCP Search Integration" - Background setup
**Estimated Time**: 30 minutes

## Objective

Write a failing integration test that establishes an SSE connection to `/mcp/sse` endpoint.

## Files to Modify

- `tests/integration/test_mcp_sse.py` (create new)

## Implementation Steps

1. Create test file structure:
```python
import pytest
import json
from httpx import AsyncClient

@pytest.mark.smoke
@pytest.mark.asyncio
async def test_sse_connection_established(test_api_client: AsyncClient):
    """Test that SSE connection to /mcp/sse endpoint succeeds."""
    # Arrange
    headers = {
        "X-API-Key": "sk-test-valid-key",
        "Accept": "text/event-stream"
    }

    # Act
    async with test_api_client.stream("POST", "/mcp/sse", headers=headers) as response:
        # Assert
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream"

        # Read first SSE event (server info)
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                assert "jsonrpc" in data
                break
```

2. Add test fixtures in `tests/conftest.py` if needed:
```python
@pytest.fixture
async def test_api_client(test_db):
    """Async HTTP client for API testing."""
    from app.main import app
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
```

## Verification

Run test (should FAIL with 404):
```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_sse_connection_established -v
```

**Expected Output**:
```
FAILED tests/integration/test_mcp_sse.py::test_sse_connection_established - httpx.HTTPStatusError: 404 Not Found
```

## Success Criteria

- Test file created
- Test executes and fails with expected error (404 Not Found)
- Error message is clear and actionable

## Next Task

Task 1.2: Add MCP SDK dependency to enable implementation
