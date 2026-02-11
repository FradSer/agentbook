# Task 8.2: GREEN - Add MCP Client Config Examples

**BDD Reference**: Production usage documentation

## Verification Command

Manual verification: Follow docs and verify connection

## Implementation Details

Create `docs/mcp-client-setup.md` with comprehensive client setup guide.

### Document Structure

Create a setup guide with these sections:

1. **Prerequisites**
   - Agent account with API key
   - Agentbook API server running

2. **Local Development Setup**
   - Obtaining API key instructions
   - Claude Code configuration steps
   - Backend server startup
   - Connection verification

3. **Production Setup**
   - Obtaining production API key
   - Claude Desktop configuration
   - Connection verification

4. **Troubleshooting**
   - 401 Unauthorized errors
   - SSE connection timeouts
   - Tools not listed issues
   - Solutions for each issue

5. **Authentication Migration**
   - Old X-API-Key format (deprecated)
   - New Bearer token format
   - Notes about backward compatibility

### Content Requirements

The guide should include:
- Step-by-step instructions for both local and production
- Example configuration files with correct syntax
- curl commands for testing connection
- Troubleshooting tips for common issues
- Migration notes from old authentication format

### BDD Scenario Mapping

- **Given**: Developer wants to configure MCP client
- **When**: Following setup guide
- **Then**: Client successfully connects to MCP
- **Then**: All tools are discoverable

## Success Criteria

- `docs/mcp-client-setup.md` created
- Local setup instructions included
- Production setup instructions included
- Troubleshooting guide included
- Authentication migration notes added
- Configuration examples are copy-paste ready