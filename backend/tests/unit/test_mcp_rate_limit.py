"""Rate-limit contract for MCP public tools.

After the public-memory pivot, `search` over MCP is anonymous and must be
throttled the same way the REST `/v1/search` endpoint is — otherwise a
runaway MCP client could burn embedding credits and hammer the DB unchecked.

These tests exercise `dispatch_tool` directly so we cover both the
authenticated and anonymous paths without spinning up the SDK session
manager.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from mcp.server import Server

from backend.core.mcp_rate_limit import mcp_search_limiter
from backend.domain.models import Agent
from backend.presentation.mcp.context import current_agent as _current_agent_ctx
from backend.presentation.mcp.context import (
    current_remote_addr as _current_remote_addr_ctx,
)
from backend.presentation.mcp.tools import dispatch_tool


@pytest.fixture(autouse=True)
def _reset_mcp_context():
    """Reset both ContextVars between tests so state does not leak."""
    agent_token = _current_agent_ctx.set(None)
    addr_token = _current_remote_addr_ctx.set(None)
    try:
        yield
    finally:
        _current_remote_addr_ctx.reset(addr_token)
        _current_agent_ctx.reset(agent_token)


@pytest.fixture()
def enable_mcp_limiter():
    """Opt the test into MCP rate-limit enforcement (disabled in the conftest)."""
    original = mcp_search_limiter.enabled
    mcp_search_limiter.enabled = True
    mcp_search_limiter.reset()
    try:
        yield
    finally:
        mcp_search_limiter.enabled = original
        mcp_search_limiter.reset()


def _make_mock_server() -> Server:
    service = MagicMock()
    service.search_problems.return_value = {"results": [], "total": 0}
    service.inspect_resource.return_value = {
        "type": "problem",
        "problem_id": str(uuid4()),
    }

    server = Server("agentbook-ratelimit-test")
    server._service = service
    server._agent = None
    return server


async def _search_once(server: Server) -> dict:
    result = await dispatch_tool(server, "search", {"query": "err"})
    return json.loads(result[0]["text"])


@pytest.mark.asyncio
async def test_given_anonymous_mcp_caller_when_search_hits_31st_request_then_response_is_rate_limited(enable_mcp_limiter):
    server = _make_mock_server()
    _current_remote_addr_ctx.set("203.0.113.7")

    payloads = [await _search_once(server) for _ in range(31)]

    success_count = sum(1 for p in payloads if "results" in p)
    throttled = [p for p in payloads if p.get("error") == "rate_limit_exceeded"]

    assert success_count == 30, f"Expected 30 successful calls, got {success_count}"
    assert len(throttled) == 1
    assert "30 requests per minute" in throttled[0]["detail"]
    assert throttled[0]["error"] == "rate_limit_exceeded"


@pytest.mark.asyncio
async def test_authenticated_caller_has_independent_quota(enable_mcp_limiter):
    """Anonymous saturation on a shared IP should not starve authenticated agents."""
    server = _make_mock_server()
    _current_remote_addr_ctx.set("203.0.113.7")

    # Burn the anonymous IP bucket.
    for _ in range(30):
        await _search_once(server)
    throttled = await _search_once(server)
    assert throttled["error"] == "rate_limit_exceeded"

    agent = Agent(api_key_hash="hash", model_type="test")
    _current_agent_ctx.set(agent)
    server._agent = agent

    response = await _search_once(server)
    assert "results" in response, f"Authenticated caller was starved: {response}"


@pytest.mark.asyncio
async def test_given_search_bucket_is_exhausted_when_inspecting_then_inspect_is_not_throttled(enable_mcp_limiter):
    """`inspect` is cheaper than `search` — the 30/min bucket must not cover it."""
    server = _make_mock_server()
    _current_remote_addr_ctx.set("203.0.113.7")

    for _ in range(30):
        await _search_once(server)
    throttled = await _search_once(server)
    assert throttled["error"] == "rate_limit_exceeded"

    result = await dispatch_tool(server, "inspect", {"id": str(uuid4())})
    payload = json.loads(result[0]["text"])
    assert payload.get("type") == "problem"
    server._service.inspect_resource.assert_called_once()


@pytest.mark.asyncio
async def test_given_limiter_disabled_by_default_when_searching_then_calls_are_not_throttled():
    """Sanity: the autouse conftest fixture keeps the MCP limiter off by default."""
    server = _make_mock_server()
    _current_remote_addr_ctx.set("203.0.113.7")

    for _ in range(60):
        payload = await _search_once(server)
        assert "results" in payload

    assert server._service.search_problems.call_count == 60


@pytest.mark.asyncio
async def test_given_rate_limited_search_when_dispatch_returns_text_message_then_payload_shape_is_stable(enable_mcp_limiter):
    server = _make_mock_server()
    _current_remote_addr_ctx.set("203.0.113.99")

    for _ in range(30):
        await _search_once(server)

    result = await dispatch_tool(server, "search", {"query": "err"})

    assert len(result) == 1
    assert result[0]["type"] == "text"
    payload = json.loads(result[0]["text"])
    assert payload["error"] == "rate_limit_exceeded"
    assert "detail" in payload
