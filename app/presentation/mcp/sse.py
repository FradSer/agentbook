"""MCP SSE (Server-Sent Events) transport endpoint.

Implements MCP protocol over SSE for agent runtime integration.
Reference: https://spec.modelcontextprotocol.io/specification/transports/sse/
"""

from __future__ import annotations

from fastapi import APIRouter
from sse_starlette import EventSourceResponse

sse_router = APIRouter()


@sse_router.get("/mcp/sse")
async def mcp_sse_endpoint() -> EventSourceResponse:
    """MCP SSE transport endpoint.

    Returns Server-Sent Events stream for MCP protocol communication.
    This is the entry point for MCP-compatible agents (Claude Code, Claude Desktop).

    Returns:
        EventSourceResponse with text/event-stream content type
    """
    async def event_generator():
        """Generate SSE events for MCP protocol.

        Currently returns minimal connection acknowledgment.
        Tool implementations will be added in subsequent milestones.
        """
        # Send initial connection acknowledgment
        # In a full MCP implementation, this would handle:
        # - initialize handshake
        # - tools/list requests
        # - tools/call invocations
        yield {
            "event": "message",
            "data": "MCP SSE connection established"
        }

    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )
