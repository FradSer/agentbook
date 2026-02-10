# Task 1.4: GREEN - Implement SSE Transport with FastAPI Mounting

**BDD Reference**: Feature "MCP SSE Connection Management" - Scenario "Successful SSE connection establishment"

## Verification Command
```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_sse_connection_established -v
```

**Expected Result**: Task 1.1 test passes

## Implementation Notes

### 1. Create `app/presentation/mcp/router.py`

```python
"""FastAPI router for mounting MCP Starlette app.

Integrates FastMCP's SSE and message endpoints into the FastAPI application.
"""

from __future__ import annotations

from fastapi import APIRouter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


mcp_router = APIRouter(prefix="/mcp")


def mount_mcp_app(router: APIRouter, mcp_server: FastMCP) -> None:
    """Mount the FastMCP Starlette app onto the FastAPI router.

    This function is called during app initialization in app/main.py.

    Args:
        router: FastAPI router to mount the MCP app onto
        mcp_server: Configured FastMCP server instance
    """
    starlette_app = mcp_server.sse_app()
    router.mount("", starlette_app, name="mcp")
```

### 2. Update `app/main.py`

Import and mount MCP server:

```python
from app.presentation.mcp.router import mcp_router, mount_mcp_server
from app.presentation.mcp.server import create_mcp_server

def create_app() -> FastAPI:
    app = FastAPI(...)
    # ... existing CORS and service setup ...

    # Include existing API routes
    app.include_router(api_router)

    # Include and mount MCP routes
    app.include_router(mcp_router)
    mcp_server = create_mcp_server(app.state.service)
    mount_mcp_app(mcp_router, mcp_server)

    return app
```

### 3. Update `app/presentation/mcp/__init__.py`

```python
"""MCP (Model Context Protocol) presentation layer.

This module provides SSE-based MCP endpoints for agent runtime integration.
Follows Clean Architecture: all business logic is delegated to AgentbookService.
"""

from __future__ import annotations

__all__ = ["mcp_router"]

from app.presentation.mcp.router import mcp_router
```

## Success Criteria
- `app/presentation/mcp/router.py` created
- `app/main.py` updated to mount MCP server
- `app/presentation/mcp/__init__.py` updated
- Task 1.1 test passes
- SSE connection can be established at `/mcp/sse`