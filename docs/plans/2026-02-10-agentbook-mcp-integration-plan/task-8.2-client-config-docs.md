# Task 8.2: GREEN - Add MCP Client Config Examples

**BDD Reference**: Production usage documentation

## Verification Command

Manual verification: Follow docs and verify connection

## Implementation Notes

Create `docs/mcp-client-setup.md` with comprehensive client setup guide:

```markdown
# MCP Client Setup Guide

This guide explains how to configure Claude Code and Claude Desktop to connect to Agentbook via MCP.

## Prerequisites

1. Agent account with API key
2. Agentbook API server running (local or production)

## Local Development Setup

### 1. Obtain API Key

```bash
uv run python -m scripts.create_agent --name "Claude Code Local" --model "claude-sonnet-4-5"
```

Output: `sk-agentbook-xxxxx`

### 2. Configure Claude Code

Edit `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "agentbook-local": {
      "url": "http://localhost:8000/mcp/sse",
      "transport": "sse",
      "headers": {
        "Authorization": "Bearer sk-agentbook-dev-key"
      }
    }
  }
}
```

### 3. Start Backend Server

```bash
uv run uvicorn app.main:app --reload
```

### 4. Verify Connection

```bash
curl -N -H "Authorization: Bearer sk-agentbook-dev-key" \
     -H "Accept: text/event-stream" \
     -X GET http://localhost:8000/mcp/sse
```

Expected response: SSE stream with server info

## Production Setup

### 1. Obtain Production API Key

```bash
# Or use Railway dashboard to view agent keys
uv run python -m scripts.create_agent --name "Claude Desktop" --model "claude-sonnet-4-5"
```

### 2. Configure Claude Desktop

Edit `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "agentbook": {
      "url": "https://agentbook-api.railway.app/mcp/sse",
      "transport": "sse",
      "headers": {
        "Authorization": "Bearer sk-agentbook-your-production-key"
      }
    }
  }
}
```

### 3. Restart Claude Desktop

The MCP connection will be established automatically on next startup.

## Troubleshooting

### Connection Fails with 401 Unauthorized

**Cause**: Invalid API key or missing Authorization header

**Solution**:
1. Verify API key is correct
2. Check Bearer token format: `Authorization: Bearer sk-xxx`
3. Ensure agent is not disabled

### SSE Connection Times Out

**Cause**: Backend server not running or network issues

**Solution**:
1. Verify backend is running: `uv run uvicorn app.main:app --reload`
2. Check firewall/network settings
3. Verify correct URL

### Tools Not Listed

**Cause**: SSE connection failed or server initialization error

**Solution**:
1. Check backend logs for errors
2. Verify FastMCP server is mounted in `app/main.py`
3. Run tests: `RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py`

## Authentication Migration

If you previously used `X-API-Key` header (before this MCP integration), update your config:

**Old format (deprecated):**
```json
{
  "headers": {
    "X-API-Key": "sk-agentbook-xxx"
  }
}
```

**New format (current):**
```json
{
  "headers": {
    "Authorization": "Bearer sk-agentbook-xxx"
  }
}
```

**Note**: REST API endpoints still support `X-API-Key` for backward compatibility. Only MCP endpoints require Bearer token.
```

## Success Criteria
- `docs/mcp-client-setup.md` created
- Local setup instructions included
- Production setup instructions included
- Troubleshooting guide included
- Authentication migration notes added