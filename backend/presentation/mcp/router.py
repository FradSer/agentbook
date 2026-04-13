"""MCP (Model Context Protocol) router for SSE transport.

Mounts MCP SSE app using SseServerTransport with authentication.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from backend.presentation.mcp.auth import get_verifier

sse_router = APIRouter()

_sse_app = None
_mcp_server = None


def setup_mcp_app(service) -> None:
    """Initialize MCP server with SSE transport.

    Args:
        service: AgentbookService instance
    """
    global _sse_app, _mcp_server

    from mcp.server import Server
    from mcp.server.sse import SseServerTransport

    from backend.presentation.mcp.tools import register_tools

    # Create MCP server
    _mcp_server = Server("agentbook")

    # Inject services (agent will be set per-request from auth)
    _mcp_server._service = service
    _mcp_server._agent = None

    register_tools(_mcp_server)
    # Create SSE transport
    _sse_transport = SseServerTransport("/mcp/messages/")

    # Mount the SSE handlers
    @sse_router.get("/sse")
    async def handle_sse(request: Request):
        """SSE endpoint for MCP protocol.

        SSE is the legacy transport and keeps auth-required at the connection
        level. Anonymous reads should use the Streamable HTTP transport at
        `/mcp`, which honours per-tool auth via the dispatcher.
        """
        verifier = get_verifier(request)

        authorization = request.headers.get("Authorization")
        x_api_key = request.headers.get("X-API-Key")

        agent = verifier.verify(authorization=authorization, x_api_key=x_api_key)

        _mcp_server._agent = agent

        async with _sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await _mcp_server.run(
                streams[0], streams[1], _mcp_server.create_initialization_options()
            )
        return Response()

    @sse_router.post("/messages/{session_id}")
    async def handle_messages(request: Request, session_id: str):
        """Message endpoint for MCP protocol."""
        await _sse_transport.handle_post_message(request, session_id)
        return Response()
