# Task 9.2: Cleanup - Remove Old MCP Router

**BDD Reference**: N/A (cleanup task)

## Verification Command

```bash
! grep -q "sse_router" app/presentation/api/router.py
```

**Expected Result**: Command succeeds (sse_router not found in file)

## Implementation Details

Remove references to the old `sse_router` from the FastAPI router.

### File to Modify

`app/presentation/api/router.py`

### Removal Steps

1. Remove import statement:
   - Remove `from app.presentation.mcp.sse import router as sse_router`

2. Remove router registration:
   - Remove `app.include_router(sse_router, prefix="/v1", tags=["SSE"])`

### Verification Steps

After removal, verify:
1. No references to `sse_router` in router.py
2. All tests still pass
3. No other code references old SSE endpoint

### Cleanup Impact

The old SSE router was replaced by the new MCP router mounted at `/mcp` prefix. REST API endpoints remain unchanged.

## Success Criteria

- `sse_router` import removed from router.py
- `sse_router` registration removed from router.py
- All tests still pass
- No other code references old SSE endpoint