# Task 1.3: [GREEN] Implement SSE endpoint

**Type**: Implementation (GREEN)
**BDD Reference**: Feature "MCP Search Integration" - SSE connection
**Estimated Time**: 45 minutes

## Objective

Create the SSE transport handler that accepts MCP connections and initializes the MCP server.

## Files to Create/Modify

- `app/presentation/mcp/__init__.py` (create)
- `app/presentation/mcp/sse.py` (create)
- `app/presentation/mcp/tools.py` (create - empty stub for now)

## Implementation Steps

### 1. Create `app/presentation/mcp/__init__.py`:
```python
"""MCP (Model Context Protocol) presentation layer."""
```

### 2. Create `app/presentation/mcp/sse.py`:
```python
"""SSE transport handler for MCP server."""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from mcp.server import Server
from mcp.server.sse import sse_server

from app.core.deps import get_service
from app.application.service import AgentbookService
from app.presentation.mcp.tools import register_mcp_tools

router = APIRouter()


@router.post("/mcp/sse")
async def handle_mcp_sse(
    request: Request,
    service: AgentbookService = Depends(get_service)
) -> StreamingResponse:
    """
    MCP Server-Sent Events endpoint.

    Establishes SSE connection for MCP protocol communication.
    Registers all Agentbook tools and handles tool execution.
    """
    # Initialize MCP server
    mcp_server = Server("agentbook")

    # Register tools (will be implemented in Task 2.3+)
    register_mcp_tools(mcp_server, service)

    # Establish SSE transport
    async with sse_server(request) as (read_stream, write_stream):
        await mcp_server.run(
            read_stream=read_stream,
            write_stream=write_stream,
            initialization_options={}
        )

    return StreamingResponse(
        write_stream,
        media_type="text/event-stream"
    )
```

### 3. Create `app/presentation/mcp/tools.py` (stub):
```python
"""MCP tool definitions."""
from mcp.server import Server
from app.application.service import AgentbookService


def register_mcp_tools(server: Server, service: AgentbookService) -> None:
    """
    Register all MCP tools with the server.

    Tools will be implemented in subsequent tasks:
    - Task 2.3: search_agentbook
    - Task 3.3: ask_question
    - Task 4.3: answer_question
    - Task 5.3: vote_answer
    """
    # Empty for now - tools added in later tasks
    pass
```

## Verification

Run Task 1.1 test (should now PASS):
```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_sse_connection_established -v
```

**Expected Output**:
```
tests/integration/test_mcp_sse.py::test_sse_connection_established PASSED [100%]
```

## Success Criteria

- SSE endpoint handler created
- MCP server initializes successfully
- Task 1.1 integration test passes
- No business logic in presentation layer (only protocol handling)

## Architecture Compliance

✅ **Clean Architecture**: Presentation layer only handles protocol, delegates to Service
✅ **Dependency Injection**: `AgentbookService` injected via `Depends(get_service)`
✅ **Zero Logic Duplication**: Tool registration stub is empty (filled in later tasks)

## Next Task

Task 1.4: Register MCP route in FastAPI router
