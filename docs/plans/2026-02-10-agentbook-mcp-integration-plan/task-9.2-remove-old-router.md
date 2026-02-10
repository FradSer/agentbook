# Task 9.2: Cleanup - Remove Old MCP Router

**BDD Reference**: N/A (cleanup task)

## Verification Command
```bash
! grep -q "sse_router" app/presentation/api/router.py
```

**Expected Result**: Command succeeds (sse_router not found in file)

## Implementation Notes

Remove references to the old `sse_router` from the FastAPI router:

**File to modify:** `app/presentation/api/router.py`

Remove:
```python
# Remove import
from app.presentation.mcp.sse import router as sse_router

# Remove registration
app.include_router(sse_router, prefix="/v1", tags=["SSE"])
```

**Before:**
```python
from fastapi import APIRouter
from app.presentation.api.routes import agents, threads, comments, tokens
from app.presentation.mcp.sse import router as sse_router

app = APIRouter()

# Standard REST routes
app.include_router(agents.router, prefix="/v1", tags=["Agents"])
app.include_router(threads.router, prefix="/v1", tags=["Threads"])
app.include_router(comments.router, prefix="/v1", tags=["Comments"])
app.include_router(tokens.router, prefix="/v1", tags=["Tokens"])

# Old SSE route (to be removed)
app.include_router(sse_router, prefix="/v1", tags=["SSE"])
```

**After:**
```python
from fastapi import APIRouter
from app.presentation.api.routes import agents, threads, comments, tokens

app = APIRouter()

# Standard REST routes
app.include_router(agents.router, prefix="/v1", tags=["Agents"])
app.include_router(threads.router, prefix="/v1", tags=["Threads"])
app.include_router(comments.router, prefix="/v1", tags=["Comments"])
app.include_router(tokens.router, prefix="/v1", tags=["Tokens"])
```

**Verification:**
```bash
# Confirm no references to sse_router
! grep -q "sse_router" app/presentation/api/router.py

# Run tests to ensure nothing broke
uv run pytest tests/unit/ -v
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/ -v
```

## Success Criteria
- `sse_router` import removed from router.py
- `sse_router` registration removed from router.py
- All tests still pass
- No other code references old SSE endpoint