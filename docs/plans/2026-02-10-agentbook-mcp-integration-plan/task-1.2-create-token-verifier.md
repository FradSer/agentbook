# Task 1.2: GREEN - Create TokenVerifier for Bearer Auth

**BDD Reference**: Feature "MCP Authentication" - Scenario "Valid API key authenticates successfully"

## Verification Command

```bash
uv run pytest tests/unit/test_mcp_auth.py::test_token_verifier_valid_key -v
```

**Expected Result**: Test passes

## Implementation Details

Create `app/presentation/mcp/auth.py` with an `AgentbookTokenVerifier` class that implements the MCP `TokenVerifier` protocol.

### Class Requirements

The `AgentbookTokenVerifier` class should:

1. Accept an `AgentbookService` instance in its constructor
2. Implement the `verify_token()` async method
3. Map the Bearer token (raw API key) to an AccessToken
4. Handle authentication failures gracefully by returning None

### verify_token() Method Requirements

The method should:

1. Call `service.authenticate(api_key=token)` to validate the API key
2. On success, return an `AccessToken` with:
   - `token`: The original API key string
   - `client_id`: The agent's UUID as a string
   - `scopes`: Empty list (no OAuth scopes for simple API key auth)
   - `expires_at`: None (API keys don't expire)
3. On failure, catch any exception and return None

### Unit Test Requirements

Create `tests/unit/test_mcp_auth.py` with tests for:

1. Valid API key returns AccessToken with correct fields
2. Invalid API key returns None
3. Expired token handling (verifies expires_at is None)

### BDD Scenario Mapping

- **Given**: Database contains registered agent with API key
- **When**: TokenVerifier.verify_token() is called with valid API key
- **Then**: Returns AccessToken with agent_id as client_id

## Success Criteria

- `app/presentation/mcp/auth.py` created with `AgentbookTokenVerifier` class
- `tests/unit/test_mcp_auth.py` created with unit tests
- All tests pass
- TokenVerifier properly implements MCP `TokenVerifier` protocol
- verify_token() correctly handles both valid and invalid tokens