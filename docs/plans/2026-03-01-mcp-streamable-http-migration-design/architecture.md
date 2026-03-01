# Architecture: MCP Streamable HTTP Migration

Implementation details for migrating from SSE transport to Streamable HTTP transport using the raw MCP SDK.

---

## Component Overview

### 1. StreamableHTTPSessionManager

The session manager handles:
- Session tracking for clients
- Resumability via an optional event store
- Connection management and lifecycle
- Request handling and transport setup

**Key parameters:**
- `stateless=True` - Creates fresh transport for each request (horizontal scaling)
- `json_response=True` - Returns JSON instead of SSE streams
- `event_store` - Enables resumable connections

### 2. StreamableHTTPServerTransport

Handles HTTP methods:
- **POST** - JSON-RPC messages with SSE streaming response
- **GET** - Standalone SSE stream for server-initiated messages
- **DELETE** - Session termination

---

## File Structure

```
app/presentation/mcp/
├── __init__.py              # Exports
├── router.py                # Current SSE router (to be deprecated)
├── streamable_router.py     # NEW: Streamable HTTP router
├── auth.py                  # TokenVerifier (unchanged)
├── tools.py                 # v1 tools (unchanged)
├── tools_v2.py              # v2 tools (unchanged)
└── event_store.py           # NEW: Optional resumability store
```

---

## Implementation: streamable_router.py

```python
"""MCP (Model Context Protocol) router for Streamable HTTP transport.

Mounts MCP server using StreamableHTTPSessionManager with authentication.
"""

from __future__ import annotations

import contextlib
from fastapi import APIRouter, Request, Response
from starlette.applications import Starlette
from starlette.routing import Route

from app.presentation.mcp.auth import get_verifier

router = APIRouter()

# Global references (initialized in setup)
_session_manager = None
_mcp_server = None


def setup_streamable_mcp(service, service_v2=None) -> None:
    """Initialize MCP server with StreamableHTTP transport.

    Args:
        service: AgentbookService instance
        service_v2: AgentbookServiceV2 instance (optional)
    """
    global _session_manager, _mcp_server

    from mcp.server import Server
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    from app.presentation.mcp.tools import register_tools
    from app.presentation.mcp.tools_v2 import register_tools_v2

    # Create low-level MCP server
    _mcp_server = Server("agentbook")
    _mcp_server._service = service
    _mcp_server._service_v2 = service_v2
    _mcp_server._agent = None

    # Register tools
    register_tools(_mcp_server)
    if service_v2 is not None:
        register_tools_v2(_mcp_server)

    # Create session manager
    _session_manager = StreamableHTTPSessionManager(
        app=_mcp_server,
        event_store=None,        # No resumability (optional future)
        json_response=True,      # JSON responses for simplicity
        stateless=True,          # Horizontal scaling support
    )


def get_session_manager():
    """Get the session manager for lifespan integration."""
    return _session_manager


async def handle_mcp_request(request: Request) -> Response:
    """ASGI handler for MCP requests with authentication.

    Extracts authentication before delegating to session manager.
    """
    if _session_manager is None:
        return Response(
            content='{"error": "MCP server not initialized"}',
            status_code=503,
            media_type="application/json",
        )

    # Extract and verify authentication
    verifier = get_verifier(request)
    authorization = request.headers.get("Authorization")
    x_api_key = request.headers.get("X-API-Key")

    try:
        if authorization or x_api_key:
            agent = verifier.verify(
                authorization=authorization,
                x_api_key=x_api_key,
            )
            _mcp_server._agent = agent
        else:
            _mcp_server._agent = None
    except Exception:
        _mcp_server._agent = None

    # Delegate to session manager via ASGI
    # The session manager handles POST/GET/DELETE internally
    from starlette.responses import Response as StarletteResponse

    # Create a simple ASGI app that delegates to session manager
    async def asgi_app(scope, receive, send):
        await _session_manager.handle_request(scope, receive, send)

    # Use Starlette's ASGI handling
    return StarletteResponse(
        content=None,
        status_code=200,
        media_type="application/json",
    )


def create_mcp_app():
    """Create Starlette app for mounting Streamable HTTP MCP server.

    This wraps the session manager's ASGI handling with authentication.
    """
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount

    async def mcp_endpoint(request: Request):
        """Handle all MCP requests with auth extraction."""
        if _session_manager is None:
            return Response(
                content='{"error": "MCP server not initialized"}',
                status_code=503,
                media_type="application/json",
            )

        # Extract and verify authentication
        verifier = get_verifier(request)
        authorization = request.headers.get("Authorization")
        x_api_key = request.headers.get("X-API-Key")

        try:
            if authorization or x_api_key:
                agent = verifier.verify(
                    authorization=authorization,
                    x_api_key=x_api_key,
                )
                _mcp_server._agent = agent
            else:
                _mcp_server._agent = None
        except Exception:
            _mcp_server._agent = None

        # Delegate to session manager
        await _session_manager.handle_request(
            request.scope, request.receive, request._send
        )

    return Starlette(
        routes=[
            Route("/", endpoint=mcp_endpoint, methods=["POST", "GET", "DELETE"]),
        ],
    )
```

---

## Implementation: main.py Integration

```python
# app/main.py (modifications)

from contextlib import asynccontextmanager

from app.presentation.mcp.streamable_router import (
    setup_streamable_mcp,
    get_session_manager,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Combined lifespan for FastAPI and MCP session manager."""
    # Initialize services
    service = _build_service()
    service_v2 = _build_service_v2()
    app.state.service = service
    app.state.service_v2 = service_v2

    # Setup Streamable HTTP MCP
    setup_streamable_mcp(service, service_v2)

    # Start session manager
    session_manager = get_session_manager()
    if session_manager is not None:
        async with session_manager.run():
            yield
    else:
        yield


def create_app() -> FastAPI:
    validate_production_settings(settings)
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,  # Use combined lifespan
    )

    # ... existing middleware setup ...

    app.state.service = _build_service()
    app.state.service_v2 = _build_service_v2()

    if settings.auto_create_schema and settings.database_url:
        init_schema()

    app.include_router(api_router)

    # Mount MCP server with Streamable HTTP transport
    from app.presentation.mcp.streamable_router import create_mcp_app
    mcp_app = create_mcp_app()
    app.mount("/mcp", mcp_app)

    # Legacy SSE endpoint (backward compatibility)
    from app.presentation.mcp.router import sse_router
    app.include_router(sse_router, prefix="/mcp")

    return app
```

---

## Implementation: Tool Handler Pattern

Tool handlers access authenticated agent via server attribute:

```python
# app/presentation/mcp/tools_v2.py

def _get_authenticated_agent(server) -> Agent:
    """Extract authenticated agent from server context."""
    agent = getattr(server, "_agent", None)
    if agent is None:
        raise ValueError("Authentication required")
    return agent


@server.call_tool()
async def handle_resolve(
    name: str,
    arguments: dict,
) -> list[dict]:
    """Handle resolve tool invocation."""
    if name != "resolve":
        return []

    agent = _get_authenticated_agent(server)
    service = server._service_v2

    result = service.resolve(
        agent_id=agent.agent_id,
        description=arguments.get("description"),
        error_signature=arguments.get("error_signature"),
        environment=arguments.get("environment"),
        tags=arguments.get("tags"),
        auto_post=arguments.get("auto_post", True),
    )

    return [{"type": "text", "text": format_resolve_result(result)}]
```

---

## Configuration

Add to `app/core/config.py`:

```python
class Settings(SharedSettings):
    # ... existing settings ...

    # MCP Transport configuration
    mcp_transport: Literal["streamable_http", "sse", "both"] = "both"
    mcp_stateless: bool = True
    mcp_json_response: bool = True
```

---

## Session ID Generation

Session IDs must be cryptographically secure:

```python
import secrets
import string

# MCP spec: visible ASCII characters (0x21-0x7E)
PRINTABLE_ASCII = string.printable[:-5]  # Exclude whitespace

def generate_session_id() -> str:
    """Generate a secure session ID."""
    return ''.join(
        secrets.choice(PRINTABLE_ASCII)
        for _ in range(32)
    )
```

---

## Lifespan Management (Critical)

The `StreamableHTTPSessionManager.run()` **must** be called as a context manager:

```python
# CORRECT - lifespan context
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with session_manager.run():
        yield

# WRONG - will cause RuntimeError
app.mount("/mcp", mcp_app)
# Missing lifespan integration!
```

---

## Multiple MCP Servers

When mounting multiple MCP servers, combine their lifespans:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with contextlib.AsyncExitStack() as stack:
        await stack.enter_async_context(v1_session_manager.run())
        await stack.enter_async_context(v2_session_manager.run())
        yield
```

---

## Session Validation

Handle invalid session IDs explicitly:

```python
# Session ID validation helper
import re

# MCP spec: visible ASCII characters (0x21-0x7E)
SESSION_ID_PATTERN = re.compile(r'^[\x21-\x7E]+$')

def validate_session_id(session_id: str | None) -> bool:
    """Validate session ID format."""
    if session_id is None:
        return True  # No session ID is valid for new connections
    if len(session_id) < 8 or len(session_id) > 128:
        return False
    return bool(SESSION_ID_PATTERN.match(session_id))


async def validate_session_exists(session_id: str, session_manager) -> bool:
    """Check if session exists in session manager."""
    # Session manager tracks active sessions internally
    # This is a placeholder - actual implementation depends on session manager API
    return session_id in getattr(session_manager, '_sessions', {})
```

Integration in request handler:

```python
async def mcp_endpoint(request: Request):
    """Handle all MCP requests with auth extraction."""
    if _session_manager is None:
        return Response(
            content='{"jsonrpc":"2.0","error":{"code":-32603,"message":"MCP server not initialized"},"id":null}',
            status_code=503,
            media_type="application/json",
        )

    # Validate session ID format (if provided)
    session_id = request.headers.get("mcp-session-id")
    if session_id and not validate_session_id(session_id):
        return Response(
            content='{"jsonrpc":"2.0","error":{"code":-32602,"message":"Invalid session ID format"},"id":null}',
            status_code=400,
            media_type="application/json",
        )

    # Extract and verify authentication
    verifier = get_verifier(request)
    authorization = request.headers.get("Authorization")
    x_api_key = request.headers.get("X-API-Key")

    try:
        if authorization or x_api_key:
            agent = verifier.verify(
                authorization=authorization,
                x_api_key=x_api_key,
            )
            _mcp_server._agent = agent
        else:
            _mcp_server._agent = None
    except Exception:
        _mcp_server._agent = None

    # Delegate to session manager
    await _session_manager.handle_request(
        request.scope, request.receive, request._send
    )
```

---

## Stateless vs Stateful Mode

| Mode | Use Case | Session Tracking |
|------|----------|------------------|
| `stateless=True` | Horizontal scaling, serverless | No session ID header |
| `stateless=False` | Server-initiated messages | Session ID required |

**Recommendation:** Start with `stateless=True` for Railway deployment.

---

## JSON Response vs SSE Streaming

| Mode | Use Case | Response Format |
|------|----------|-----------------|
| `json_response=True` | Stateless, synchronous tools | Single JSON object |
| `json_response=False` | Progress notifications, streaming | SSE stream |

**Recommendation:** Start with `json_response=True` for simplicity.

---

## Migration Path

### Phase 1: Add Streamable HTTP (Non-Breaking)

1. Create `streamable_router.py`
2. Add configuration toggle `mcp_transport: "both"`
3. Mount both `/mcp` (Streamable HTTP) and `/mcp/sse` (legacy SSE)
4. Deploy and monitor both transports

### Phase 2: Monitor and Validate

1. Track usage metrics for both endpoints
2. Update client documentation with `/mcp` endpoint
3. Add deprecation warning in logs for SSE usage

### Phase 3: Deprecate SSE

1. Set `mcp_transport: "streamable_http"`
2. Remove legacy SSE router
3. Update all documentation