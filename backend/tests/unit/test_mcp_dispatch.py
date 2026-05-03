"""Unit tests for ``dispatch_tool`` in backend/presentation/mcp/tools.py.

The dispatcher enforces per-tool authorization, the anonymous-vs-auth
rate-limit split for ``recall``, and the ``unknown_tool`` fallback.
These are the contract guarantees documented in docs/mcp-setup.md and
CLAUDE.md, and they don't have direct coverage elsewhere -- the existing
``test_mcp_tool_handlers.py`` only exercises the handler functions.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from backend.core.mcp_rate_limit import mcp_search_limiter
from backend.domain.models import Agent
from backend.presentation.mcp import context as mcp_context
from backend.presentation.mcp.tools import dispatch_tool


def _server_with_service(**method_returns):
    """Build a fake server whose ``_service`` has stub methods configured
    to return the supplied values.
    """
    server = MagicMock()
    service = MagicMock()
    for method, value in method_returns.items():
        getattr(service, method).return_value = value
    server._service = service
    return server


def _payload(result):
    return json.loads(result[0]["text"])


@pytest.mark.asyncio
async def test_unknown_tool_returns_unknown_tool_error() -> None:
    server = _server_with_service()
    result = await dispatch_tool(server, "no_such_tool", {})
    assert _payload(result)["error"] == "unknown_tool"


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", ["remember", "report", "verify"])
async def test_write_tools_require_authentication(tool_name: str) -> None:
    """Anonymous callers hitting any write tool get 'unauthorized'."""
    server = _server_with_service()
    token = mcp_context.current_agent.set(None)
    try:
        result = await dispatch_tool(server, tool_name, {"solution_id": str(uuid4())})
    finally:
        mcp_context.current_agent.reset(token)

    body = _payload(result)
    assert body["error"] == "unauthorized"
    assert "ak_" in body["detail"]


@pytest.mark.asyncio
async def test_recall_delegates_to_service_search_problems() -> None:
    server = _server_with_service(
        search_problems={"results": [], "total": 0},
    )
    result = await dispatch_tool(server, "recall", {"query": "pgvector"})

    server._service.search_problems.assert_called_once_with(
        query="pgvector", error_log=None, limit=5
    )
    assert _payload(result) == {"results": [], "total": 0}


@pytest.mark.asyncio
async def test_recall_returns_rate_limit_error_when_limiter_exhausted(
    enable_mcp_limiter,
) -> None:
    server = _server_with_service(
        search_problems={"results": [], "total": 0},
    )
    # Exhaust the anonymous bucket -- 30/minute by contract.
    for _ in range(mcp_search_limiter.max_calls):
        await dispatch_tool(server, "recall", {"query": "q"})

    result = await dispatch_tool(server, "recall", {"query": "q"})
    body = _payload(result)
    assert body["error"] == "rate_limit_exceeded"
    assert "per minute" in body["detail"]


@pytest.mark.asyncio
async def test_verify_invalid_uuid_returns_invalid_input() -> None:
    server = _server_with_service()
    agent = Agent(api_key_hash="h", model_type="t")
    token = mcp_context.current_agent.set(agent)
    try:
        result = await dispatch_tool(server, "verify", {"solution_id": "not-a-uuid"})
    finally:
        mcp_context.current_agent.reset(token)

    body = _payload(result)
    assert body["error"] == "invalid_input"
    assert "UUID" in body["detail"]


@pytest.mark.asyncio
async def test_verify_missing_solution_id_returns_invalid_input() -> None:
    server = _server_with_service()
    agent = Agent(api_key_hash="h", model_type="t")
    token = mcp_context.current_agent.set(agent)
    try:
        result = await dispatch_tool(server, "verify", {})
    finally:
        mcp_context.current_agent.reset(token)

    body = _payload(result)
    assert body["error"] == "invalid_input"
    assert "solution_id" in body["detail"]


@pytest.mark.asyncio
async def test_trace_routes_to_inspect_handler_with_not_found_passthrough() -> None:
    from backend.application.errors import NotFoundError

    server = _server_with_service()
    server._service.inspect_resource.side_effect = NotFoundError("nope")

    result = await dispatch_tool(server, "trace", {"id": str(uuid4())})
    assert _payload(result)["error"] == "not_found"


@pytest.mark.asyncio
async def test_trace_invalid_uuid_returns_invalid_input() -> None:
    server = _server_with_service()
    result = await dispatch_tool(server, "trace", {"id": "not-a-uuid"})
    body = _payload(result)
    assert body["error"] == "invalid_input"
