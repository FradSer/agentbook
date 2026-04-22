"""Shared MCP rate-limit bucket across legacy + new names.

search and recall MUST share the 30/minute bucket so callers cannot bypass
the limit by alternating tool names.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from backend.core.mcp_rate_limit import (
    mcp_search_limiter,
    mcp_search_limiter_auth,
)
from backend.presentation.mcp.context import current_remote_addr
from backend.presentation.mcp.tools import dispatch_tool
from backend.tests.conftest import _build_service


def _reset_limiters() -> None:
    mcp_search_limiter.enabled = True
    mcp_search_limiter_auth.enabled = True
    mcp_search_limiter.reset()
    mcp_search_limiter_auth.reset()


def _payload(result) -> dict:
    return json.loads(result[0]["text"])


@pytest.mark.parametrize(
    ("first_tool", "second_tool", "remote_addr"),
    [
        ("search", "recall", "10.0.0.1"),
        ("recall", "search", "10.0.0.2"),
    ],
)
def test_given_legacy_and_new_names_when_bucket_is_exhausted_then_alias_call_is_rate_limited(
    first_tool: str, second_tool: str, remote_addr: str
) -> None:
    _reset_limiters()
    service, _ = _build_service()
    server = SimpleNamespace(_service=service, _agent=None)

    token = current_remote_addr.set(remote_addr)
    try:
        for _ in range(30):
            asyncio.run(dispatch_tool(server, first_tool, {"query": "q"}))
        result = asyncio.run(dispatch_tool(server, second_tool, {"query": "q"}))
    finally:
        current_remote_addr.reset(token)

    body = _payload(result)
    assert body.get("error") == "rate_limit_exceeded"
