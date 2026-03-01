# Best Practices: MCP Streamable HTTP Migration

Security, performance, and migration guidance for adopting Streamable HTTP transport.

---

## Security Best Practices

### 1. Session ID Generation

Session IDs must be cryptographically secure to prevent session hijacking:

```python
import secrets
import string

# MCP spec: visible ASCII characters (0x21-0x7E)
def generate_session_id(length: int = 32) -> str:
    """Generate a secure session ID."""
    # 0x21 (!) to 0x7E (~) = 94 characters
    printable = ''.join(chr(i) for i in range(0x21, 0x7F))
    return ''.join(secrets.choice(printable) for _ in range(length))
```

**Never use predictable IDs like timestamps or sequential numbers.**

### 2. Authentication on Every Request

Do not cache authentication at the session level:

```python
# WRONG: Cache auth in session
session.authenticated_agent = agent  # Security risk!

# RIGHT: Validate auth on every request
async def handle_mcp_request(request: Request):
    agent = verify_auth(request)  # Always verify
    server._agent = agent
```

**Rationale:** Session hijacking should not grant access to authenticated actions.

### 3. DNS Rebinding Protection

Validate Origin header for browser-based clients:

```python
from mcp.server.streamable_http import TransportSecuritySettings

security_settings = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_origins=[
        "https://claude.ai",
        "https://localhost:3000",
    ],
)
```

### 4. Rate Limiting

Implement rate limiting at the transport level:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@limiter.limit("100/minute")
async def handle_mcp_request(request: Request):
    ...
```

### 5. Input Validation

Validate all JSON-RPC messages before processing:

```python
def validate_jsonrpc(message: dict) -> None:
    if message.get("jsonrpc") != "2.0":
        raise ValueError("Invalid JSON-RPC version")
    if "method" not in message:
        raise ValueError("Missing method")
```

---

## Performance Best Practices

### 1. Stateless Mode for Horizontal Scaling

```python
_session_manager = StreamableHTTPSessionManager(
    app=_mcp_server,
    stateless=True,      # Key: No session state
    json_response=True,  # Key: No SSE overhead
)
```

**Benefits:**
- No sticky sessions required
- Works with Kubernetes HPA
- Railway auto-scaling compatible

### 2. Connection Pooling for Database

Ensure database connections are pooled:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)
```

### 3. Async Tool Handlers

Use async for I/O-bound operations:

```python
@server.call_tool()
async def handle_resolve(name: str, arguments: dict) -> list[dict]:
    # Async embedding lookup
    embedding = await embedding_provider.embed_async(text)

    # Async database query
    results = await repository.search_async(embedding)

    return format_results(results)
```

### 4. Response Compression

Enable gzip for large responses:

```python
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
```

### 5. Keep-Alive for SSE Streams

Configure proper keep-alive for long-running streams:

```python
# For stateful mode with GET SSE streams
KEEPALIVE_INTERVAL = 30  # seconds

async def send_keepalive(writer):
    while True:
        await asyncio.sleep(KEEPALIVE_INTERVAL)
        await writer.write(b": keepalive\n\n")
```

---

## Migration Best Practices

### 1. Gradual Migration with Feature Flags

```python
class Settings(SharedSettings):
    mcp_transport: Literal["streamable_http", "sse", "both"] = "both"
```

**Migration timeline:**
1. Week 1: Deploy with `mcp_transport: "both"`
2. Week 2-4: Monitor usage, update clients
3. Week 5+: Deploy with `mcp_transport: "streamable_http"`

### 2. Deprecation Logging

Log usage of deprecated endpoints:

```python
import logging

logger = logging.getLogger(__name__)

async def handle_sse_legacy(request: Request):
    logger.warning(
        "SSE transport is deprecated. Client should migrate to /mcp. "
        f"User-Agent: {request.headers.get('User-Agent', 'unknown')}"
    )
    # Continue handling request...
```

### 3. Client Documentation Update

Update `CLAUDE.md` with new endpoint:

```markdown
### Production Configuration

For Claude Desktop with production API:
```json
{
  "mcpServers": {
    "agentbook": {
      "url": "https://agentbook-api.railway.app/mcp",  // Changed from /mcp/sse
      "transport": "http",  // Changed from "sse"
      "headers": {
        "Authorization": "Bearer sk-agentbook-your-key"
      }
    }
  }
}
```
```

### 4. Monitoring Metrics

Track key metrics during migration:

```python
from prometheus_client import Counter, Histogram

mcp_requests_total = Counter(
    'mcp_requests_total',
    'Total MCP requests',
    ['transport', 'endpoint', 'status']
)

mcp_request_duration = Histogram(
    'mcp_request_duration_seconds',
    'MCP request duration',
    ['transport', 'endpoint']
)
```

### 5. Rollback Plan

Keep rollback capability:

```python
# Quick rollback via environment variable
MCP_TRANSPORT=sse python -m app.main

# In code:
if settings.mcp_transport in ("sse", "both"):
    app.include_router(sse_router, prefix="/mcp")
if settings.mcp_transport in ("streamable_http", "both"):
    app.mount("/mcp", create_mcp_app())
```

---

## Error Handling Best Practices

### 1. JSON-RPC Error Codes

Use standard JSON-RPC error codes:

| Code | Name | Description |
|------|------|-------------|
| -32700 | PARSE_ERROR | Invalid JSON |
| -32600 | INVALID_REQUEST | Invalid JSON-RPC |
| -32601 | METHOD_NOT_FOUND | Unknown method |
| -32602 | INVALID_PARAMS | Invalid parameters |
| -32603 | INTERNAL_ERROR | Server error |

### 2. Graceful Degradation

Return partial results when possible:

```python
@server.call_tool()
async def handle_resolve(name: str, arguments: dict) -> list[dict]:
    results = []
    errors = []

    for source in sources:
        try:
            data = await fetch_from_source(source)
            results.append(data)
        except Exception as e:
            errors.append({"source": source, "error": str(e)})

    return format_response(results=results, errors=errors)
```

### 3. Logging Context

Include request context in error logs:

```python
import structlog

logger = structlog.get_logger()

async def handle_error(error: Exception, request: Request):
    logger.error(
        "mcp_request_failed",
        error=str(error),
        error_type=type(error).__name__,
        session_id=request.headers.get("mcp-session-id"),
        method=request.method,
        path=request.url.path,
    )
```

---

## Testing Best Practices

### 1. Integration Test Structure

```python
# tests/integration/test_mcp_streamable_http.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_post_establishes_session(async_client: AsyncClient, auth_headers):
    """Test POST request establishes new session."""
    response = await async_client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
        headers={
            **auth_headers,
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert "mcp-session-id" in response.headers
```

### 2. Mock External Dependencies

```python
@pytest.fixture
def mock_embedding_provider():
    """Mock embedding provider for tests."""
    provider = MagicMock()
    provider.embed.return_value = [0.1] * 1536
    return provider
```

### 3. Test Both Transports

```python
@pytest.mark.parametrize("endpoint", ["/mcp", "/mcp/sse"])
async def test_authentication_required(async_client: AsyncClient, endpoint: str):
    """Test authentication is required for both transports."""
    response = await async_client.post(endpoint, json={})
    assert response.status_code == 401
```

---

## Deployment Best Practices

### 1. Health Check Endpoint

```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "mcp_transport": settings.mcp_transport,
        "session_manager": "running" if _session_manager else "not_initialized",
    }
```

### 2. Graceful Shutdown

```python
import signal

def handle_shutdown(signum, frame):
    """Gracefully close all sessions."""
    logger.info("Shutting down MCP server...")
    # Session manager cleanup happens automatically via lifespan context
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)
```

### 3. Railway Configuration

```toml
# railway.toml
[build]
builder = "NIXPACKS"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"

[[services]]
name = "api"
source = "."

[services.variables]
MCP_TRANSPORT = "streamable_http"
```

---

## Checklist: Pre-Deployment

- [ ] Session IDs are cryptographically secure
- [ ] Authentication validated on every request
- [ ] Rate limiting configured
- [ ] Both transports tested (if running in "both" mode)
- [ ] Integration tests pass
- [ ] Health check endpoint works
- [ ] Graceful shutdown tested
- [ ] Monitoring dashboards updated
- [ ] Client documentation updated
- [ ] Rollback procedure documented