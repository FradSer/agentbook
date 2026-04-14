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


def test_sse_authenticated_bearer_passes_auth_and_reaches_transport(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A valid bearer token passes auth and the handler reaches `connect_sse`.

    The legacy 1146-line SSE integration suite was removed in the pivot, so
    this is the lone guarantee that an authenticated GET `/mcp/sse` makes it
    past the `TokenVerifier` gate and into the SSE transport. We stub
    `SseServerTransport.connect_sse` to raise immediately instead of entering
    the indefinite MCP run loop — a sync TestClient has no clean way to close
    a live SSE stream, but short-circuiting the transport lets us verify the
    auth flow end-to-end.
    """
    from mcp.server.sse import SseServerTransport

    import backend.presentation.mcp.router as sse_module

    register = client.post("/v1/auth/register", json={"model_type": "sse-smoke-test"})
    assert register.status_code == 201, register.text
    api_key = register.json()["api_key"]

    calls: list[str] = []

    class _ShortCircuitCM:
        async def __aenter__(self):
            calls.append("entered")
            raise RuntimeError("sse-test-shortcut")

        async def __aexit__(self, *exc_info):
            return False

    def _stub_connect_sse(self, scope, receive, send):
        calls.append("connect_sse-invoked")
        return _ShortCircuitCM()

    monkeypatch.setattr(SseServerTransport, "connect_sse", _stub_connect_sse)

    try:
        client.get("/mcp/sse", headers={"Authorization": f"Bearer {api_key}"})
    except RuntimeError as exc:
        assert "sse-test-shortcut" in str(exc)

    assert calls == ["connect_sse-invoked", "entered"], (
        f"Auth gate did not forward to the SSE transport: {calls}"
    )
    assert sse_module._mcp_server._agent is not None
    assert sse_module._mcp_server._agent.model_type == "sse-smoke-test"
