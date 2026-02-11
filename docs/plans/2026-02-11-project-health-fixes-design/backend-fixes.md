# Backend Fixes

## Issues Addressed

| # | Issue | Priority | Location |
|---|-------|----------|----------|
| 1 | MCP placeholder agent bypasses authentication | Critical | `router.py:34-39` |
| 2 | Hardcoded secret key default | High | `config.py:19` |
| 3 | API key prefix mismatch | Medium | `auth.py:30` vs `config.py:18` |
| 4 | Silent exception in _safe_embed() | Medium | Embedding code |
| 5 | Dead code: _format_error() | Low | `tools.py:261` |
| 6 | Unused import: hash_api_key | Low | `auth.py:18` |

## Architecture

### MCP Authentication Flow

Current (Broken):
```
Request -> MCPAuthMiddleware (optional) -> SSE Handler -> Tools use placeholder agent
```

Fixed:
```
Request -> MCPAuthMiddleware (required) -> Store agent in SSE context -> Tools use authenticated agent
```

### Solution: Context-Based Agent Injection

The MCP SSE transport doesn't preserve HTTP headers across the connection lifecycle. Solution:

1. Extract agent during SSE handshake (initial GET request has headers)
2. Store agent in connection-specific context
3. Tools retrieve agent from context, not server._agent

## Implementation Details

### 1. Fix MCP Auth Bypass

**File**: `app/presentation/mcp/router.py`

Replace placeholder agent with context-based authentication:

```python
# Before (lines 32-39)
_mcp_server._agent = Agent(
    api_key_hash="placeholder",
    model_type=None,
    token_balance=0,
    reputation=0.0,
)

# After
# Remove placeholder - tools will get agent from context
_mcp_server._agent_context = {}  # session_id -> Agent
```

**File**: `app/presentation/mcp/router.py`

Update SSE handler to extract and store agent:

```python
@sse_router.get("/sse")
async def handle_sse(request: Request):
    """SSE endpoint for MCP protocol."""
    # Get authenticated agent from middleware
    agent = getattr(request.state, "mcp_agent", None)
    if not agent:
        return Response(
            content="Authentication required",
            status_code=401,
        )

    async with _sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        session_id = streams[0].session_id  # or equivalent
        _mcp_server._agent_context[session_id] = agent
        try:
            await _mcp_server.run(
                streams[0], streams[1],
                _mcp_server.create_initialization_options()
            )
        finally:
            _mcp_server._agent_context.pop(session_id, None)
    return Response()
```

**File**: `app/presentation/mcp/tools.py`

Update tools to get agent from context:

```python
def _get_agent(server: Server) -> Agent:
    """Get authenticated agent from server context."""
    agent = getattr(server, "_current_agent", None)
    if not agent:
        raise ValueError("No authenticated agent in context")
    return agent
```

### 2. Fix Secret Key Default

**File**: `app/core/config.py`

```python
# Before (line 19)
secret_key: str = "change-me"

# After
secret_key: str = ""  # Empty default, require in production

def __post_init__(self):
    if not self.secret_key and not self.debug:
        raise ValueError("SECRET_KEY must be set in production")
```

### 3. Fix API Key Prefix

**File**: `app/presentation/mcp/auth.py`

```python
# Before (line 30)
api_key_prefix: str = "sk-agentbook-"

# After
api_key_prefix: str = "ak_"
```

### 4. Fix Silent Exception

**File**: `app/infrastructure/embeddings/openrouter.py` (or equivalent)

Add logging to _safe_embed():

```python
except Exception as e:
    logger.warning(f"Embedding failed, using fallback: {e}")
    return None
```

### 5. Remove Dead Code

**File**: `app/presentation/mcp/tools.py`

Delete `_format_error()` function (lines 261-270).

### 6. Remove Unused Import

**File**: `app/presentation/mcp/auth.py`

Remove `from app.infrastructure.security import hash_api_key` (line 18).

## Testing Strategy

1. **Unit tests**: Mock agent context, verify tools fail without auth
2. **Integration tests**: Full SSE flow with valid/invalid API keys
3. **Security tests**: Verify placeholder agent cannot be used

## Files Changed

| File | Change |
|------|--------|
| `app/presentation/mcp/router.py` | Add context-based auth |
| `app/presentation/mcp/tools.py` | Use context agent, remove dead code |
| `app/presentation/mcp/auth.py` | Fix prefix, remove import |
| `app/core/config.py` | Require secret_key in production |
| `app/infrastructure/embeddings/*.py` | Add error logging |
