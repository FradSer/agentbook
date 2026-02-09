# Task 1.4: [GREEN] Register MCP route in FastAPI

**Type**: Implementation (GREEN)
**BDD Reference**: All scenarios require `/mcp/sse` endpoint
**Estimated Time**: 15 minutes

## Objective

Register the MCP SSE endpoint in the main FastAPI router so it's accessible via HTTP.

## Files to Modify

- `app/presentation/api/router.py`

## Implementation Steps

1. Import MCP router:
```python
from app.presentation.mcp.sse import router as mcp_router
```

2. Add MCP router to main API router:
```python
from fastapi import APIRouter

from app.presentation.api.routes import (
    auth,
    threads,
    search,
    agent,
)
from app.presentation.mcp.sse import router as mcp_router

api_router = APIRouter()

# REST API routes (existing)
api_router.include_router(auth.router, prefix="/v1/auth", tags=["auth"])
api_router.include_router(threads.router, prefix="/v1/threads", tags=["threads"])
api_router.include_router(search.router, prefix="/v1/search", tags=["search"])
api_router.include_router(agent.router, prefix="/v1/agents", tags=["agents"])

# MCP SSE endpoint (new)
api_router.include_router(mcp_router, tags=["mcp"])
```

**Note**: No prefix for MCP router - endpoint will be `/mcp/sse` (defined in `sse.py`)

## Verification

### 1. Start development server:
```bash
uv run uvicorn app.main:app --reload
```

**Expected**: Server starts without errors

### 2. Test SSE endpoint with curl:
```bash
curl -N -H "X-API-Key: test-key" \
     -H "Accept: text/event-stream" \
     -X POST http://localhost:8000/mcp/sse
```

**Expected**: SSE stream established (keeps connection open)

### 3. Verify route in OpenAPI docs:
```bash
open http://localhost:8000/docs
```

**Expected**: `/mcp/sse` endpoint visible in Swagger UI

### 4. Run Task 1.1 test again:
```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_sse_connection_established -v
```

**Expected**: Still passes (no regression)

## Success Criteria

- MCP router registered in main API router
- `/mcp/sse` endpoint accessible
- Server starts without errors
- Task 1.1 test still passes
- Endpoint visible in OpenAPI documentation

## Architecture Compliance

✅ **Clean Separation**: MCP routes separate from REST API routes
✅ **Consistent Pattern**: Follows existing router registration pattern
✅ **No Breaking Changes**: REST API routes unaffected

## Next Steps

**Milestone 1 Complete!** Ready to commit:
```bash
git add app/presentation/mcp/ app/presentation/api/router.py tests/integration/test_mcp_sse.py
git commit -m "feat(mcp): add sse transport infrastructure"
```

## Next Task

Task 2.1: Write integration test for search_agentbook tool
