# Task 1.2: [GREEN] Add MCP SDK dependency

**Type**: Infrastructure (GREEN)
**BDD Reference**: Infrastructure requirement for all scenarios
**Estimated Time**: 10 minutes

## Objective

Add the MCP SDK to project dependencies to enable SSE transport implementation.

## Files to Modify

- `pyproject.toml`

## Implementation Steps

1. Add `mcp` to dependencies list:
```toml
[project]
dependencies = [
    "alembic==1.14.0",
    "fastapi==0.115.0",
    # ... existing dependencies ...
    "mcp>=1.0.0",  # Add this line
    "uvicorn[standard]==0.32.0",
]
```

2. Sync dependencies:
```bash
uv sync
```

## Verification

Run verification command:
```bash
uv run python -c "import mcp.server; from mcp.server.sse import sse_server; print('MCP SDK installed successfully')"
```

**Expected Output**:
```
MCP SDK installed successfully
```

## Success Criteria

- `mcp` package added to `pyproject.toml`
- `uv sync` completes without errors
- Import verification succeeds
- No version conflicts with existing dependencies

## Notes

- Pin to a specific MCP version once we verify compatibility
- MCP SDK provides `mcp.server.Server` and `mcp.server.sse.sse_server`
- Check MCP documentation for latest stable version

## Next Task

Task 1.3: Implement SSE endpoint handler
