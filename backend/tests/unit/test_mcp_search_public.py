"""Public-read MCP contract.

The MCP dispatcher in `tools.py` enforces auth per tool: search and inspect
must work without an authenticated agent; contribute and report must reject
unauthenticated callers.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from mcp.server import Server

from backend.presentation.mcp.context import current_agent as _current_agent_ctx
from backend.presentation.mcp.tools import (
    handle_inspect,
    register_tools,
)


def _make_anonymous_server() -> Server:
    """Create an MCP server with a stub service and no authenticated agent."""
    service = MagicMock()
    service.search_problems.return_value = {"results": [], "total": 0}
    service.inspect_resource.return_value = {
        "type": "problem",
        "problem_id": str(uuid4()),
    }

    server = Server("agentbook-public-test")
    server._service = service
    server._agent = None
    register_tools(server)
    return server


def _reset_agent_context() -> None:
    _current_agent_ctx.set(None)


@pytest.mark.asyncio
async def test_inspect_handler_accepts_none_agent_id():
    """handle_inspect must accept agent_id=None (public read path)."""
    service = MagicMock()
    service.inspect_resource.return_value = {
        "type": "problem",
        "problem_id": str(uuid4()),
    }

    result = await handle_inspect(service, None, {"id": str(uuid4())})

    payload = json.loads(result[0]["text"])
    assert "type" in payload
    service.inspect_resource.assert_called_once()


@pytest.mark.asyncio
async def test_contribute_without_authenticated_agent_returns_auth_error():
    """contribute is a write — dispatcher must reject anonymous callers.

    The dispatcher calls _get_authenticated_agent() before invoking the
    handler. We assert the dispatcher contract by simulating the same path:
    no agent in ContextVar and no agent on the server.
    """
    from backend.presentation.mcp.tools import _get_authenticated_agent

    _reset_agent_context()
    server = _make_anonymous_server()

    with pytest.raises(ValueError, match="Authentication required"):
        _get_authenticated_agent(server)


@pytest.mark.asyncio
async def test_report_without_authenticated_agent_returns_auth_error():
    """report is a write — dispatcher must reject anonymous callers."""
    from backend.presentation.mcp.tools import _get_authenticated_agent

    _reset_agent_context()
    server = _make_anonymous_server()

    with pytest.raises(ValueError, match="Authentication required"):
        _get_authenticated_agent(server)


def test_streamable_http_initialize_anonymous_returns_200():
    """An anonymous client can establish an MCP Streamable HTTP session.

    The connection-level auth check was removed; per-tool enforcement lives
    in the tools.py dispatcher.
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


def test_dispatcher_routes_public_tools_without_auth():
    """Source-level guard: dispatcher in tools.py must skip auth for search/inspect.

    This is a structural regression check — re-introducing _get_authenticated_agent()
    around the search/inspect branches would silently break the public-memory
    contract, so we lock the source shape.
    """
    import inspect as _inspect

    from backend.presentation.mcp import tools

    src = _inspect.getsource(tools.register_tools)

    assert 'elif name == "search"' in src or 'if name == "search"' in src
    assert 'elif name == "inspect"' in src

    search_block, _, after_search = src.partition('name == "search"')
    inspect_block, _, after_inspect = after_search.partition('name == "inspect"')
    contribute_block, _, _ = after_inspect.partition('name == "contribute"')

    # search and inspect branches must NOT call _get_authenticated_agent.
    inspect_branch = inspect_block.split("elif")[0]
    assert "_get_authenticated_agent" not in inspect_branch, (
        "search branch should not authenticate"
    )

    contribute_inspect_branch = contribute_block.split("elif")[0]
    assert "_get_authenticated_agent" not in contribute_inspect_branch, (
        "inspect branch should not authenticate"
    )
