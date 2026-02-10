# Task 1.1: RED - Write Integration Test for SSE Connection

**BDD Reference**: Feature "MCP SSE Connection Management" - Scenario "Successful SSE connection establishment"

## Verification Command
```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_sse_connection_established -v
```

**Expected Result**: Test fails with "404 Not Found" (endpoint not implemented yet)

## Implementation Notes

Create a minimal integration test that:
1. Starts the FastAPI app
2. Attempts to connect to `/mcp/sse` with `Authorization: Bearer sk-test-key`
3. Verifies the response has:
   - HTTP 200 status
   - `Content-Type: text/event-stream`
   - `Cache-Control: no-cache`
   - `X-Accel-Buffering: no`
4. Reads SSE stream and expects endpoint event with message path

## Test File
`tests/integration/test_mcp_sse.py`

```python
import pytest
from httpx import AsyncClient

from app.main import create_app


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_sse_connection_established() -> None:
    """Test SSE connection establishment with Bearer token authentication.

    BDD Reference: Scenario "Successful SSE connection establishment"

    Given: FastAPI backend is running at http://localhost:8000
    And: Agent has valid API key
    When: Agent sends GET request to /mcp/sse with Authorization: Bearer sk-test-key
    Then: Connection returns HTTP 200 OK
    And: Response has Content-Type: text/event-stream
    And: Response has Cache-Control: no-cache
    And: Response has X-Accel-Buffering: no
    And: SSE stream sends endpoint event with message path
    """
    app = create_app()

    # Setup: Create test agent with API key
    from app.domain.models import Agent
    from datetime import datetime, timedelta
    from uuid import uuid4

    from app.infrastructure.persistence.in_memory import InMemoryAgentRepository

    agent_repo = InMemoryAgentRepository()
    agent = Agent(
        agent_id=uuid4(),
        api_key_hash="hash-of-test-key",
        model_type="test-model",
        token_balance=100,
        reputation=1.0,
        created_at=datetime.utcnow(),
        last_active_at=datetime.utcnow(),
    )
    agent_repo.add(agent)

    # Mock the service to use in-memory repo
    from unittest.mock import Mock
    mock_service = Mock()
    mock_service.authenticate = lambda api_key, agent_info=None: agent

    # Monkey-patch the app state
    app.state.service = mock_service

    async with AsyncClient(app=app, base_url="http://test") as client:
        with client.stream("GET", "/mcp/sse", headers={
            "Authorization": "Bearer sk-test-key"
        }) as response:
            assert response.status_code == 200, "SSE endpoint should return 200 OK"
            assert response.headers["content-type"] == "text/event-stream"
            assert response.headers["cache-control"] == "no-cache"
            assert response.headers.get("x-accel-buffering") == "no"

            # Read SSE events
            events = []
            async for line in response.aiter_lines():
                if line.startswith("event: "):
                    events.append(line)
                if line.startswith("data: "):
                    break  # Stop after first data

            # Verify endpoint event
            assert any("endpoint" in e for e in events)
```

## Success Criteria
- Test file created at `tests/integration/test_mcp_sse.py`
- Test fails as expected (endpoint not implemented)
- Test properly verifies all SSE headers