"""Smoke tests for the legacy SSE MCP transport.

After the public-memory pivot, `/mcp` (Streamable HTTP) is anonymous-friendly
while `/mcp/sse` keeps connection-level auth for backward compatibility. The
large SSE integration suite was removed, but the route still ships in
deployment — these smoke tests guarantee that the endpoint is mounted and
rejects unauthenticated and invalid-key callers before opening a stream.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    # Module-scoped to avoid rebuilding app + lifespan per test. The
    # autouse settings isolator in conftest is function-scoped and fires
    # after module setup, so we override here before create_app() reads them.
    from backend.core.config import settings

    settings.database_url = None
    settings.openrouter_api_key = None
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({}, id="no-auth"),
        pytest.param(
            {"Authorization": "Bearer not-an-agentbook-key"}, id="malformed-bearer"
        ),
        pytest.param(
            {"Authorization": "Bearer ak_completely-fake-key"}, id="unknown-bearer"
        ),
        pytest.param({"X-API-Key": "ak_still-not-a-real-key"}, id="unknown-x-api-key"),
    ],
)
def test_sse_rejects_unauthorized(client: TestClient, headers: dict[str, str]) -> None:
    response = client.get("/mcp/sse", headers=headers)

    assert response.status_code == 401, response.text
