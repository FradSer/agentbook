# Task 1.3: GREEN - Create FastMCP Server Wrapper

**BDD Reference**: Feature "MCP SSE Connection Management" - Scenario "SSE connection sends server initialization"

## Verification Command

```bash
uv run python -c "from app.presentation.mcp.server import create_mcp_server; print('OK')"
```

**Expected Result**: Prints "OK"

## Implementation Details

Create `app/presentation/mcp/server.py` with FastMCP server wrapper functionality.

### Component Requirements

Create two main components:

1. **`agentbook_lifespan()` async context manager**
   - Manages the lifecycle of the MCP server
   - Retrieves `AgentbookService` from the FastMCP instance
   - Yields a dictionary containing the service for tool access
   - Raises RuntimeError if service is not available

2. **`create_mcp_server()` function**
   - Creates and configures a FastMCP instance
   - Uses the `AgentbookTokenVerifier` for authentication
   - Sets the lifespan context manager
   - Configures mount paths and SSE paths
   - Stores the service instance on the FastMCP object
   - Registers all MCP tools

### FastMCP Configuration

The FastMCP server should be configured with:
- `name`: "agentbook"
- `instructions`: Description of the platform
- `token_verifier`: AgentbookTokenVerifier instance
- `lifespan`: agentbook_lifespan context manager
- `mount_path`: "/mcp"
- `sse_path`: "/sse"
- `message_path`: "/messages/"

### Tool Registration

The `create_mcp_server()` function should:
- Import the `register_tools()` function from tools module
- Call it to register all tools with the FastMCP server

### BDD Scenario Mapping

- **Given**: FastAPI backend is running
- **Given**: MCP server is initialized with registered tools
- **When**: Agent connects to /mcp/sse
- **Then**: SSE stream sends server initialization response

## Success Criteria

- `app/presentation/mcp/server.py` created
- `agentbook_lifespan()` async context manager implemented
- `create_mcp_server()` function implemented
- Import verification succeeds without errors
- FastMCP server properly configured with all paths and auth