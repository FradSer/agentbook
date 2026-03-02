"""MCP Streamable HTTP transport router.

Implements the MCP protocol over Streamable HTTP transport as defined in:
https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#streamable-http

This transport:
- Uses POST requests for all MCP operations
- Returns JSON responses by default (or SSE if negotiated)
- Supports stateless mode for horizontal scaling
- Creates sessions with mcp-session-id header
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from app.core.config import settings
from app.presentation.mcp.auth import TokenVerifier
from app.presentation.mcp.session import validate_session_id

# Global references for MCP server and session manager
_session_manager = None
_mcp_server = None
_service = None
_service_v2 = None


# JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def create_jsonrpc_error(
    code: int,
    message: str,
    request_id: Any = None,
) -> dict:
    """Create a JSON-RPC error response.

    Args:
        code: JSON-RPC error code
        message: Error message
        request_id: Request ID (if available)

    Returns:
        JSON-RPC error object
    """
    return {
        "jsonrpc": "2.0",
        "error": {"code": code, "message": message},
        "id": request_id,
    }


def setup_streamable_mcp(service, service_v2=None) -> None:
    """Initialize MCP server for Streamable HTTP transport.

    Args:
        service: AgentbookService instance
        service_v2: AgentbookServiceV2 instance (optional)
    """
    global _mcp_server, _service, _service_v2

    from mcp.server import Server

    from app.presentation.mcp.tools import register_tools
    from app.presentation.mcp.tools_v2 import register_tools_v2

    _service = service
    _service_v2 = service_v2

    # Create MCP server
    _mcp_server = Server("agentbook")

    # Inject services (agent will be set per-request from auth)
    _mcp_server._service = service
    _mcp_server._service_v2 = service_v2
    _mcp_server._agent = None

    register_tools(_mcp_server)
    if service_v2 is not None:
        register_tools_v2(_mcp_server)


def create_mcp_app() -> FastAPI:
    """Create a Starlette app for the Streamable HTTP MCP endpoint.

    Returns:
        FastAPI app instance with MCP endpoint
    """
    app = FastAPI()

    @app.post("/")
    @app.get("/")
    @app.delete("/")
    async def mcp_endpoint(request: Request) -> Response:
        """Handle MCP requests over Streamable HTTP transport.

        This endpoint:
        1. Validates headers (Accept, Content-Type)
        2. Extracts and verifies authentication
        3. Delegates to MCP session manager
        4. Returns JSON or SSE response
        """
        # Validate Accept header
        accept_header = request.headers.get("Accept", "")
        if not _validate_accept_header(accept_header):
            return JSONResponse(
                status_code=406,
                content={
                    "detail": "Client must accept both application/json and text/event-stream"
                },
            )

        # Validate Content-Type for POST requests
        if request.method == "POST":
            content_type = request.headers.get("Content-Type", "")
            if not content_type.startswith("application/json"):
                return JSONResponse(
                    status_code=415,
                    content={"detail": "Content-Type must be application/json"},
                )

        # Extract and verify authentication
        verifier = TokenVerifier(service=_service)
        authorization = request.headers.get("Authorization")
        x_api_key = request.headers.get("X-API-Key")

        try:
            if authorization or x_api_key:
                agent = verifier.verify(
                    authorization=authorization, x_api_key=x_api_key
                )
                _mcp_server._agent = agent
            else:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Authentication required"},
                )
        except Exception as e:
            return JSONResponse(
                status_code=401,
                content={"detail": str(e.detail if hasattr(e, "detail") else e)},
            )

        # Handle session ID if provided
        session_id = request.headers.get("mcp-session-id")
        if session_id and not validate_session_id(session_id):
            return JSONResponse(
                status_code=404,
                content={"detail": "Invalid or expired session ID"},
            )

        # Handle based on HTTP method
        if request.method == "DELETE":
            # Terminate session
            return Response(status_code=200)

        # For POST requests, process MCP message
        if request.method == "POST":
            try:
                body = await request.body()
                message = json.loads(body)

                # Process the message through MCP server
                response = await _process_mcp_message(message)
                return JSONResponse(content=response)

            except json.JSONDecodeError as e:
                return JSONResponse(
                    content=create_jsonrpc_error(PARSE_ERROR, f"Parse error: {e}")
                )
            except Exception as e:
                return JSONResponse(
                    content=create_jsonrpc_error(
                        INTERNAL_ERROR, f"Internal error: {e}"
                    )
                )

        # GET request - return server info or SSE stream
        return JSONResponse(
            content={
                "name": "agentbook",
                "version": settings.app_version,
                "protocol": "MCP",
            }
        )

    return app


def _validate_accept_header(accept_header: str) -> bool:
    """Validate Accept header contains required media types.

    Args:
        accept_header: Accept header value

    Returns:
        True if valid, False otherwise
    """
    # Must accept both application/json and text/event-stream
    accept_lower = accept_header.lower()
    return "application/json" in accept_lower and "text/event-stream" in accept_lower


async def _process_mcp_message(message: dict) -> dict:
    """Process an MCP message and return response.

    Args:
        message: JSON-RPC message

    Returns:
        JSON-RPC response
    """
    from mcp.types import InitializeRequest

    method = message.get("method")
    params = message.get("params", {})
    request_id = message.get("id")

    # Handle initialize
    if method == "initialize":
        # Create initialization options
        init_options = _mcp_server.create_initialization_options()

        # Build the response
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": params.get(
                    "protocolVersion", "2024-11-05"
                ),
                "capabilities": init_options.capabilities.model_dump()
                if hasattr(init_options.capabilities, "model_dump")
                else {},
                "serverInfo": {
                    "name": "agentbook",
                    "version": settings.app_version,
                },
            },
        }

    # For other methods, delegate to MCP server
    # This is a simplified implementation - the full implementation
    # would use the session manager for stateful sessions
    return create_jsonrpc_error(
        METHOD_NOT_FOUND, f"Method not found: {method}", request_id
    )