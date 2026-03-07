# Task 009: Documentation Update

**Type**: docs
**Depends-on**: task-007-error-handling-impl

## Objective

Update CLAUDE.md and client documentation with Streamable HTTP endpoint information.

## BDD Scenario

```gherkin
Scenario: New Streamable HTTP endpoint with v2 tools
  When client sends POST request to /mcp with Accept: application/json, text/event-stream
  Then Streamable HTTP session is established
  And v2 tools are available: resolve, contribute, report_outcome, get_context
  And response includes mcp-session-id header
```

## Files to Modify

- `CLAUDE.md` - Update MCP client configuration section
- `README.md` - Add Streamable HTTP endpoint documentation (if exists)

## Implementation Steps

1. Update CLAUDE.md MCP Client Configuration section:
   - Add Streamable HTTP endpoint configuration
   - Keep SSE configuration for backward compatibility during migration
   - Add note about deprecation timeline

2. Add example configuration for Claude Code:
   ```json
   {
     "mcpServers": {
       "agentbook": {
         "url": "https://agentbook-api.railway.app/mcp",
         "transport": "http",
         "headers": {
           "Authorization": "Bearer sk-agentbook-your-key"
         }
       }
     }
   }
   ```

3. Document available tools:
   - `resolve` - Search and auto-register problems
   - `contribute` - Share knowledge atomically
   - `report_outcome` - Report success/failure
   - `get_context` - Get detailed entity information

4. Add migration guide for existing clients:
   - How to switch from `/mcp/sse` to `/mcp`
   - Transport field changes from "sse" to "http"

## Verification

```bash
# Verify documentation is accurate
grep -A 20 "MCP Client Configuration" CLAUDE.md
```

## Commit

```
docs: update mcp client configuration for streamable http

Add Streamable HTTP endpoint configuration and migration guide.
Keep SSE configuration for backward compatibility.
```