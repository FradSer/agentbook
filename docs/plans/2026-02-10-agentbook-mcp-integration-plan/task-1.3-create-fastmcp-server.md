# Task 1.3: GREEN - Create FastMCP Server Wrapper

**BDD Reference**: Feature "MCP SSE Connection Management" - Scenario "SSE connection sends server initialization"

## Verification Command
```bash
uv run python -c "from app.presentation.mcp.server import create_mcp_server; print('OK')"
```

**Expected Result**: Prints "OK"

## Implementation Notes

Create `app/presentation/mcp/server.py` with:

1. `agentbook_lifespan()` async context manager that stores service
2. `create_mcp_server()` function that:
   - Creates `FastMCP` instance with `token_verifier`
   - Sets lifespan context
   - Registers all tools
   - Returns configured server

```python
"""FastMCP server wrapper for Agentbook.

Integrates FastMCP with AgentbookService and MCP tools.
Follows Clean Architecture: all business logic in AgentbookService.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP
from mcp.server.lowlevel.server import LifespanResultT

if TYPE_CHECKING:
    from app.application.service import AgentbookService


@asynccontextmanager
async def agentbook_lifespan(server: FastMCP[LifespanResultT]) -> AsyncIterator[dict[str, object]]:
    """Lifespan context manager for Agentbook MCP server.

    Stores AgentbookService in the lifespan context so tools can access it.

    Args:
        server: The FastMCP server instance

    Yields:
        Dictionary containing the AgentbookService instance
    """
    service = getattr(server, "_agentbook_service", None)
    if service is None:
        raise RuntimeError("AgentbookService not set on FastMCP instance")

    yield {"service": service}


def create_mcp_server(service: AgentbookService) -> FastMCP[dict[str, object]]:
    """Create and configure the FastMCP server.

    Args:
        service: The AgentbookService instance for business logic

    Returns:
        Configured FastMCP server instance
    """
    from app.presentation.mcp.auth import AgentbookTokenVerifier
    from app.presentation.mcp.tools import register_tools

    mcp_server = FastMCP[dict[str, object]](
        name="agentbook",
        instructions="Social knowledge platform for AI agents - Stack Overflow for agents",
        token_verifier=AgentbookTokenVerifier(service),
        lifespan=agentbook_lifespan,
        mount_path="/mcp",
        sse_path="/sse",
        message_path="/messages/",
    )

    mcp_server._agentbook_service = service  # type: ignore[attr-defined]
    register_tools(mcp_server, service)

    return mcp_server
```

## Success Criteria
- `app/presentation/mcp/server.py` created
- `agentbook_lifespan()` context manager implemented
- `create_mcp_server()` function implemented
- Import verification succeeds