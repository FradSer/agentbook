"""MCP Streamable HTTP transport using SDK's StreamableHTTPSessionManager.

Implements the MCP protocol over Streamable HTTP transport as defined in:
https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#streamable-http
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

from fastapi.responses import JSONResponse
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.types import Receive, Scope, Send

from backend.core.config import settings
from backend.presentation.mcp.auth import current_auth_error, resolve_mcp_credentials
from backend.presentation.mcp.context import current_agent, current_remote_addr

_session_manager = None
_service = None

# JSON-RPC methods the MCP server actually serves. A request naming anything
# else is "Method not found" (-32601) — surfaced at the transport edge because
# the SDK request union would otherwise collapse it into a -32602 params error,
# which a client cannot distinguish from a known method called with bad params.
_KNOWN_MCP_METHODS = frozenset(
    {
        "initialize",
        "ping",
        "tools/list",
        "tools/call",
        "resources/list",
        "resources/read",
        "resources/templates/list",
        "resources/subscribe",
        "resources/unsubscribe",
        "prompts/list",
        "prompts/get",
        "logging/setLevel",
        "completion/complete",
    }
)


def _unknown_method_error(body: bytes) -> dict | None:
    """Return a -32601 JSON-RPC error envelope when *body* names an unknown
    method, else ``None``.

    Notifications (``notifications/*``) and any malformed / non-request body are
    passed through untouched so the SDK still owns -32700 parse errors and
    notification handling. Only a well-formed request object whose ``method`` is
    neither known nor a notification is intercepted.
    """
    try:
        payload = json.loads(body)
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    method = payload.get("method")
    if not isinstance(method, str) or method in _KNOWN_MCP_METHODS:
        return None
    if method.startswith("notifications/"):
        return None
    return {
        "jsonrpc": "2.0",
        "id": payload.get("id"),
        "error": {
            "code": -32601,
            "message": f"Method not found: {method}",
        },
    }


def setup_streamable_mcp(service) -> None:
    """Initialize MCP server and session manager for Streamable HTTP transport."""
    global _session_manager, _service

    from mcp.server import Server
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    from backend.presentation.mcp.tools import register_tools

    _service = service

    mcp_server = Server("agentbook")
    mcp_server._service = service

    register_tools(mcp_server)

    _session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
        json_response=settings.mcp_json_response,
        stateless=settings.mcp_stateless,
    )


@asynccontextmanager
async def streamable_http_lifespan():
    """Context manager for session manager lifecycle. Use in app lifespan."""
    async with _session_manager.run():
        yield


async def handle_mcp_request(scope: Scope, receive: Receive, send: Send) -> None:
    """ASGI handler for MCP Streamable HTTP requests.

    Validates Accept/Content-Type headers, authenticates the caller, sets the
    per-request agent ContextVar, then delegates to the SDK session manager.
    """
    if scope["type"] != "http":
        return

    request = Request(scope, receive)

    # Validate Accept header before auth (protocol error takes precedence)
    accept = request.headers.get("Accept", "")
    if "application/json" not in accept or "text/event-stream" not in accept:
        response = JSONResponse(
            status_code=406,
            content={
                "detail": "Client must accept both application/json and text/event-stream"
            },
        )
        await response(scope, receive, send)
        return

    # Validate Content-Type for POST requests
    if request.method == "POST":
        ct = request.headers.get("Content-Type", "")
        if not ct.startswith("application/json"):
            response = JSONResponse(
                status_code=415,
                content={"detail": "Content-Type must be application/json"},
            )
            await response(scope, receive, send)
            return

    # Reject an unknown JSON-RPC method at the transport edge with -32601
    # "Method not found". The SDK request union collapses an unparseable method
    # name into a -32602 params error, which a client cannot tell apart from a
    # known method called with bad params. Buffer the body to inspect the
    # method, then replay it to the SDK via a one-shot receive.
    if request.method == "POST":
        body = await request.body()

        async def _replay_receive() -> dict:
            return {"type": "http.request", "body": body, "more_body": False}

        receive = _replay_receive
        method_error = _unknown_method_error(body)
        if method_error is not None:
            await JSONResponse(status_code=200, content=method_error)(
                scope, receive, send
            )
            return

    # Authenticate (optional — public tools work without credentials).
    # Per-tool enforcement lives in tools.py dispatcher; only remember/report/
    # verify require an authenticated agent. recall/trace read the public memory.
    # A malformed or invalid credential must not lock the caller out of the
    # public tools (recall/trace): resolve as anonymous and record the cause so
    # the dispatcher can emit the differentiated `unauthorized` detail when a
    # write tool is invoked.
    agent, auth_failure = resolve_mcp_credentials(
        _service, request.headers.get("Authorization")
    )

    agent_token = current_agent.set(agent)
    err_token = current_auth_error.set(auth_failure)
    addr_token = current_remote_addr.set(get_remote_address(request))
    try:
        await _session_manager.handle_request(scope, receive, send)
    finally:
        current_remote_addr.reset(addr_token)
        current_auth_error.reset(err_token)
        current_agent.reset(agent_token)
