"""MCP (Model Context Protocol) router for SSE transport.

Mounts MCP SSE app using SseServerTransport.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

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
    from app.presentation.mcp.tools import register_tools
    from app.domain.models import Agent

    # Create MCP server
    _mcp_server = Server("agentbook")

    # Inject service and a placeholder agent (will be replaced with actual auth)
    _mcp_server._service = service
    _mcp_server._agent = Agent(
        api_key_hash="placeholder",
        model_type=None,
        token_balance=0,
        reputation=0.0,
    )

    register_tools(_mcp_server)
    # Create SSE transport
    _sse_transport = SseServerTransport("/mcp/messages/")

    # Mount the SSE handlers
    @sse_router.get("/sse")
    async def handle_sse(request: Request):
        """SSE endpoint for MCP protocol."""
        async with _sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await _mcp_server.run(
                streams[0], streams[1],
                _mcp_server.create_initialization_options()
            )
        return Response()

    @sse_router.post("/messages/{session_id}")
    async def handle_messages(request: Request, session_id: str):
        """Message endpoint for MCP protocol."""
        await _sse_transport.handle_post_message(request, session_id)
        return Response()
