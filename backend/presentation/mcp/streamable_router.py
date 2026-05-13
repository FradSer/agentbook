"""MCP Streamable HTTP transport using SDK's StreamableHTTPSessionManager.

Implements the MCP protocol over Streamable HTTP transport as defined in:
https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#streamable-http
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi.responses import JSONResponse
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.types import Receive, Scope, Send

from backend.core.config import settings
from backend.presentation.mcp.auth import TokenVerifier
from backend.presentation.mcp.context import current_agent, current_remote_addr

_session_manager = None
_service = None


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

    # Authenticate (optional — public tools work without credentials).
    # Per-tool enforcement lives in tools.py dispatcher; only remember/report/
    # verify require an authenticated agent. recall/trace read the public memory.
    authorization = request.headers.get("Authorization")

    agent = None
    if authorization:
        verifier = TokenVerifier(service=_service)
        try:
            agent = verifier.verify(authorization=authorization)
        except Exception as exc:
            detail = exc.detail if hasattr(exc, "detail") else str(exc)
            response = JSONResponse(status_code=401, content={"detail": detail})
            await response(scope, receive, send)
            return

    agent_token = current_agent.set(agent)
    addr_token = current_remote_addr.set(get_remote_address(request))
    try:
        await _session_manager.handle_request(scope, receive, send)
    finally:
        current_remote_addr.reset(addr_token)
        current_agent.reset(agent_token)
