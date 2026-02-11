# Task 8.1: GREEN - Update CLAUDE.md with MCP Config

**BDD Reference**: All scenarios - local testing setup

## Verification Command

Manual verification steps:
```bash
# 1. Copy config to ~/.claude/settings.json
# 2. Start backend
uv run uvicorn app.main:app --reload

# 3. Test connection with curl
curl -N -H "Authorization: Bearer sk-agentbook-dev-key" \
     -H "Accept: text/event-stream" \
     -X GET http://localhost:8000/mcp/sse
```

**Expected Result**: SSE stream returns server info

## Implementation Details

Update the "MCP Client Configuration" section in `CLAUDE.md`.

### Required Updates

1. **Update authentication format:**
   - Change from `X-API-Key` to `Authorization: Bearer sk-xxx`

2. **Update local development config example:**
   - Show correct Bearer token format in headers
   - Include instructions for obtaining API key

3. **Update production config example:**
   - Show correct Bearer token format for production URL

4. **Document available MCP tools:**
   - List all 4 tools with parameters
   - Include use case for each tool

5. **Add testing instructions:**
   - curl command for testing SSE connection
   - Expected response format

### Sections to Update

- MCP Client Configuration (main section)
- Local Development subsection
- Available MCP Tools subsection
- Testing MCP Connection subsection
- Production Configuration subsection

### BDD Scenario Mapping

- **Given**: Developer wants to test MCP locally
- **When**: CLAUDE.md is followed
- **Then**: MCP client configured correctly
- **Then**: SSE connection works with Bearer token

## Success Criteria

- CLAUDE.md updated with Bearer token format
- Local config example provided
- Production config example provided
- Instructions for obtaining API key included
- All MCP tools documented with parameters