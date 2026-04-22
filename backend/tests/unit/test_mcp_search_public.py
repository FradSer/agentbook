"""Public-read MCP dispatcher contract.

After the public-memory pivot, the MCP dispatcher must:
- route `search` and `inspect` to their handlers without any agent context
- return an in-band {"error": "unauthorized"} payload for `contribute` and
  `report` when no agent is present in context (no exception raised, no
  service method called)

These tests exercise `dispatch_tool` directly so the routing contract is
asserted behaviourally — re-introducing an auth check around the public
branches would make the public-memory tool contract fail immediately.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from mcp.server import Server

from backend.presentation.mcp.context import current_agent as _current_agent_ctx
from backend.presentation.mcp.tools import dispatch_tool


@pytest.fixture(autouse=True)
def _reset_agent_ctx():
    """Ensure every test starts with no authenticated agent in ContextVar."""
    token = _current_agent_ctx.set(None)
    try:
        yield
    finally:
        _current_agent_ctx.reset(token)


def _make_anonymous_server() -> Server:
    service = MagicMock()
    service.search_problems.return_value = {"results": [], "total": 0}
    service.inspect_resource.return_value = {
        "type": "problem",
        "problem_id": str(uuid4()),
    }

    server = Server("agentbook-public-test")
    server._service = service
    server._agent = None
    return server


@pytest.mark.asyncio
async def test_dispatch_search_succeeds_without_auth():
    server = _make_anonymous_server()

    result = await dispatch_tool(
        server,
        "search",
        {"query": "hydration error", "error_log": "at Component.render", "limit": 3},
    )

    payload = json.loads(result[0]["text"])
    # Legacy 'search' carries deprecation _meta; strip it for payload equality.
    assert payload.pop("_meta", None) == {
        "deprecated": True,
        "replacement": "recall",
        "sunset": "2026-10-18",
    }
    assert payload == {"results": [], "total": 0}
    server._service.search_problems.assert_called_once_with(
        query="hydration error",
        error_log="at Component.render",
        limit=3,
        environment=None,
    )


@pytest.mark.asyncio
async def test_dispatch_inspect_succeeds_without_auth():
    server = _make_anonymous_server()
    target_id = uuid4()

    result = await dispatch_tool(server, "inspect", {"id": str(target_id)})

    payload = json.loads(result[0]["text"])
    assert payload["type"] == "problem"
    server._service.inspect_resource.assert_called_once_with(
        resource_id=target_id, include=None
    )


@pytest.mark.asyncio
async def test_dispatch_contribute_without_auth_returns_unauthorized():
    server = _make_anonymous_server()

    result = await dispatch_tool(
        server,
        "contribute",
        {"description": "Segfault when importing numpy on Alpine"},
    )

    payload = json.loads(result[0]["text"])
    assert payload["error"] == "unauthorized"
    assert "Authentication required" in payload.get("detail", "")
    server._service.contribute.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_report_without_auth_returns_unauthorized():
    server = _make_anonymous_server()

    result = await dispatch_tool(
        server,
        "report",
        {"solution_id": str(uuid4()), "success": True},
    )

    payload = json.loads(result[0]["text"])
    assert payload["error"] == "unauthorized"
    assert "Authentication required" in payload.get("detail", "")
    server._service.report_outcome.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_unknown_tool_returns_error_payload():
    server = _make_anonymous_server()

    result = await dispatch_tool(server, "definitely-not-a-tool", {})

    payload = json.loads(result[0]["text"])
    assert payload["error"] == "unknown_tool"


def test_streamable_http_initialize_anonymous_returns_200():
    """An anonymous client can establish an MCP Streamable HTTP session.

    Connection-level auth was removed in the public-memory pivot; per-tool
    enforcement lives in the dispatcher tested above.
    """
    from backend.main import create_app

    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "anon-test", "version": "1.0"},
                },
            },
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("jsonrpc") == "2.0"
    assert "result" in body
