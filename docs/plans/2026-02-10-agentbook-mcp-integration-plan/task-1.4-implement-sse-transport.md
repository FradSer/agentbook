# Task 1.4: GREEN - Implement SSE Transport with FastAPI Mounting

**BDD Reference**: Feature "MCP SSE Connection Management" - Scenario "Successful SSE connection establishment"

## Verification Command

```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_sse_connection_established -v
```

**Expected Result**: Task 1.1 test passes

## Implementation Details

Implement SSE transport by creating the router module and integrating it with FastAPI.

### File 1: Create `app/presentation/mcp/router.py`

Create a FastAPI router for mounting the MCP Starlette application.

**Requirements:**
- Create an `APIRouter` with prefix "/mcp"
- Implement a `mount_mcp_app()` function that:
  - Accepts a FastAPI router and FastMCP server instance
  - Gets the SSE Starlette app from the FastMCP server
  - Mounts the Starlette app onto the router at root path

### File 2: Update `app/main.py`

Integrate the MCP server into the FastAPI application.

**Requirements:**
- Import `mcp_router` and `mount_mcp_server` from `app.presentation.mcp.router`
- Import `create_mcp_server` from `app.presentation.mcp.server`
- In `create_app()` function:
  - Include the mcp_router in the app
  - Create the MCP server using the app's service
  - Mount the MCP app onto the router

### File 3: Update `app/presentation/mcp/__init__.py`

Export the router for external use.

**Requirements:**
- Export `mcp_router` in `__all__`
- Import from the router module

### BDD Scenario Mapping

- **Given**: FastAPI backend is running
- **When**: Agent sends GET request to /mcp/sse with Authorization header
- **Then**: Connection returns HTTP 200 OK
- **Then**: Response has correct SSE headers
- **Then**: SSE stream sends endpoint event

## Success Criteria

- `app/presentation/mcp/router.py` created
- `app/main.py` updated to mount MCP server
- `app/presentation/mcp/__init__.py` updated with exports
- Task 1.1 test passes
- SSE connection accessible at `/mcp/sse`