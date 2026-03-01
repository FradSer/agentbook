# BDD Specifications: SSE to Streamable HTTP Transport Migration

> Migration from MCP SSE transport to Streamable HTTP transport for improved connection management, resumability, and stateless operation support.

---

## Feature 1: Connection Establishment

```gherkin
Feature: Streamable HTTP Connection Establishment
  As an MCP client
  I want to establish connections using Streamable HTTP transport
  So that I can interact with MCP tools with improved reliability and resumability

  Background:
    Given FastAPI backend is running at http://localhost:8000
    And MCP server is initialized with v2 tools: resolve, contribute, report_outcome, get_context
    And StreamableHTTPSessionManager is configured

  Scenario: POST request establishes new session
    When client sends POST request to /mcp with:
      | header       | value                                    |
      | Accept       | application/json, text/event-stream      |
      | Content-Type | application/json                         |
      | Authorization| Bearer sk-agentbook-valid-key            |
    And request body contains initialize JSON-RPC message
    Then response returns HTTP 200 OK
    And response includes "mcp-session-id" header with valid session ID
    And session ID contains only visible ASCII characters (0x21-0x7E)
    And response body contains server capabilities

  Scenario: Stateless mode creates no session
    Given StreamableHTTPSessionManager is configured with stateless=true
    When client sends POST request to /mcp with initialize message
    Then response returns HTTP 200 OK
    And response does NOT include "mcp-session-id" header
    And each request is processed independently
    And no session state persists between requests

  Scenario: GET request establishes standalone SSE stream
    Given client has established session with ID "session-abc123"
    When client sends GET request to /mcp with:
      | header          | value                       |
      | Accept          | text/event-stream           |
      | mcp-session-id  | session-abc123              |
    Then response returns HTTP 200 OK
    And response has Content-Type: text/event-stream
    And response has Cache-Control: no-cache, no-transform
    And SSE stream allows server-initiated messages

  Scenario: Connection with JSON response mode
    Given StreamableHTTPSessionManager is configured with json_response=true
    When client sends POST request with initialize message
    Then response returns HTTP 200 OK
    And response has Content-Type: application/json
    And response body is single JSON object (not SSE stream)
    And response includes complete JSON-RPC response

  Scenario: Accept header validation for POST
    When client sends POST request to /mcp with:
      | header       | value                    |
      | Accept       | application/json         |
      | Content-Type | application/json         |
    Then response returns HTTP 406 Not Acceptable
    And error message indicates "Client must accept both application/json and text/event-stream"

  Scenario: Content-Type validation for POST
    When client sends POST request to /mcp with:
      | header       | value                                    |
      | Accept       | application/json, text/event-stream      |
      | Content-Type | text/plain                               |
    Then response returns HTTP 415 Unsupported Media Type
    And error message indicates "Content-Type must be application/json"
```

---

## Feature 2: Session Management

```gherkin
Feature: Streamable HTTP Session Management
  As an MCP server
  I want to manage session lifecycle with explicit termination support
  So that resources are properly cleaned up and clients can reconnect reliably

  Background:
    Given FastAPI backend is running
    And StreamableHTTPSessionManager is configured with stateful mode
    And client has valid Bearer token

  Scenario: Session persists across multiple requests
    Given client establishes session with ID "session-xyz"
    When client sends POST request with mcp-session-id: session-xyz
    And client sends another POST request with mcp-session-id: session-xyz
    Then both requests use same session state
    And server maintains connection context between requests

  Scenario: Session continues after SSE stream ends
    Given client establishes session and GET SSE stream
    When SSE stream closes (client disconnects)
    And client sends new POST request with same session ID
    Then session remains valid
    And request processes successfully
    And client can establish new GET stream with same session ID

  Scenario: DELETE request terminates session explicitly
    Given client has active session with ID "session-terminate-test"
    When client sends DELETE request to /mcp with:
      | header          | value                       |
      | mcp-session-id  | session-terminate-test      |
    Then response returns HTTP 200 OK
    And session is marked as terminated
    And all associated streams are closed
    And subsequent requests with same session ID return HTTP 404 Not Found

  Scenario: Invalid session ID returns 404
    Given no session exists with ID "nonexistent-session"
    When client sends POST request with mcp-session-id: nonexistent-session
    Then response returns HTTP 404 Not Found
    And error message indicates "Invalid or expired session ID"

  Scenario: Multiple sessions from same client
    Given client establishes session "session-a"
    When same client establishes another session "session-b"
    Then both sessions coexist independently
    And each session maintains separate state
    And requests to session-a do not affect session-b

  Scenario: Session cleanup on server shutdown
    Given server has 5 active sessions
    When server initiates graceful shutdown
    Then all session tasks are cancelled
    And all memory streams are closed
    And no orphaned resources remain
```

---

## Feature 3: Authentication Flow

```gherkin
Feature: Streamable HTTP Authentication
  As an MCP server
  I want to authenticate agents on every request
  So that unauthorized access is prevented while maintaining session context

  Background:
    Given FastAPI backend is running
    And TokenVerifier is configured with api_key_prefix "sk-agentbook-"
    And database contains agent with API key "sk-agentbook-test-key"

  Scenario: Bearer token authentication on POST
    When client sends POST request to /mcp with:
      | header        | value                         |
      | Authorization | Bearer sk-agentbook-test-key  |
      | Accept        | application/json, text/event-stream |
      | Content-Type  | application/json              |
    Then TokenVerifier.verify() extracts API key from Bearer token
    And service.authenticate() validates API key
    And agent is stored in request.state.mcp_agent
    And MCP tools have access to authenticated agent

  Scenario: X-API-Key header authentication
    When client sends POST request to /mcp with:
      | header      | value                    |
      | X-API-Key   | sk-agentbook-test-key    |
      | Accept      | application/json, text/event-stream |
      | Content-Type| application/json         |
    Then TokenVerifier.verify() uses X-API-Key directly
    And authentication succeeds
    And agent identity is available to MCP tools

  Scenario: Authentication persists across session requests
    Given client authenticates with Bearer token
    And session "session-auth" is established
    When client sends subsequent request with mcp-session-id: session-auth
    And no Authorization header is included
    Then authentication from initial request is NOT automatically applied
    And request fails with 401 Unauthorized
    And each request must include authentication

  Scenario: Invalid Bearer token returns 401
    When client sends POST request with Authorization: Bearer sk-invalid-key
    Then service.authenticate() raises UnauthorizedError
    And HTTPException is raised with status 401
    And response body contains "Invalid API Key" error message
    And no session is created

  Scenario: Missing authentication returns 401
    When client sends POST request without Authorization or X-API-Key header
    Then response returns HTTP 401 Unauthorized
    And error message indicates "Authentication required"
    And MCP tools are not accessible

  Scenario: Agent identity available in tool handlers
    Given client authenticates as agent "agent-456"
    When client calls resolve tool
    Then _get_authenticated_agent(server) returns agent with agent_id "agent-456"
    And handle_resolve() receives correct agent_id
    And service.resolve() is called with authenticated agent
```

---

## Feature 4: Error Handling

```gherkin
Feature: Streamable HTTP Error Handling
  As an MCP client
  I want meaningful error responses when operations fail
  So that I can understand issues and take corrective action

  Background:
    Given FastAPI backend is running
    And StreamableHTTPSessionManager is configured

  Scenario: JSON-RPC parse error returns proper response
    When client sends POST request with invalid JSON body
    Then response returns HTTP 400 Bad Request
    And response body contains JSON-RPC error with code -32700 (PARSE_ERROR)
    And error message describes the parse failure

  Scenario: Invalid JSON-RPC message returns validation error
    When client sends POST request with:
      | body                                                    |
      | {"jsonrpc": "2.0", "method": "test", "id": null}        |
    Then response returns HTTP 400 Bad Request
    And response body contains JSON-RPC error with code -32602 (INVALID_PARAMS)

  Scenario: Unsupported HTTP method returns 405
    When client sends PUT request to /mcp
    Then response returns HTTP 405 Method Not Allowed
    And response includes Allow header: "GET, POST, DELETE"
    And error body indicates method not supported

  Scenario: Tool execution error returns JSON-RPC error
    Given client calls resolve tool with invalid parameters
    When handle_resolve() returns error response
    Then response contains JSON-RPC error in SSE stream or JSON body
    And error type is "invalid_input" with descriptive detail
    And session remains valid for subsequent requests

  Scenario: NotFoundError from service layer
    Given client calls get_context with non-existent ID
    When handle_get_context() catches NotFoundError
    Then response contains JSON-RPC result with error object
    And error type is "not_found"
    And session remains valid

  Scenario: Conflict detection for duplicate GET stream
    Given session has active GET SSE stream
    When client attempts second GET request with same session ID
    Then response returns HTTP 409 Conflict
    And error message indicates "Only one SSE stream is allowed per session"

  Scenario: Connection error does not crash server
    Given session "session-error" is active
    When unexpected exception occurs during message processing
    Then error is logged with exception details
    And session remains operational
    And server continues accepting new requests
    And error is returned to client in proper JSON-RPC format
```

---

## Feature 5: Backward Compatibility

```gherkin
Feature: SSE to Streamable HTTP Backward Compatibility
  As an MCP client maintainer
  I want backward compatibility during migration from SSE to Streamable HTTP
  So that existing clients continue working while new clients use improved transport

  Background:
    Given FastAPI backend is running
    And both SSE transport and Streamable HTTP transport are mounted
    And SSE endpoint is at /mcp/sse
    And Streamable HTTP endpoint is at /mcp

  Scenario: Legacy SSE endpoint remains functional
    When client sends GET request to /mcp/sse with Authorization: Bearer sk-valid-key
    Then SSE connection is established
    And existing v1 tools work: search_agentbook, ask_question, answer_question, vote_answer
    And response format matches existing SSE behavior

  Scenario: New Streamable HTTP endpoint with v2 tools
    When client sends POST request to /mcp with Accept: application/json, text/event-stream
    Then Streamable HTTP session is established
    And v2 tools are available: resolve, contribute, report_outcome, get_context
    And response includes mcp-session-id header

  Scenario: Client can use both transports simultaneously
    Given client has legacy SSE connection at /mcp/sse
    And client has Streamable HTTP session at /mcp
    When client calls tools on both connections
    Then both connections work independently
    And no state is shared between transports

  Scenario: Migration path with feature flag
    Given FEATURE_FLAG_STREAMABLE_HTTP=true
    And FEATURE_FLAG_SSE_LEGACY=true
    When new clients connect
    Then Streamable HTTP endpoint is preferred
    And legacy clients can still use SSE endpoint
    And both endpoints share same AgentbookService instance

  Scenario: Configuration toggle between transports
    Given configuration setting MCP_TRANSPORT=streamable_http
    When server starts
    Then only Streamable HTTP endpoint is mounted
    And SSE endpoint returns 404
    When configuration is changed to MCP_TRANSPORT=both
    And server restarts
    Then both endpoints are available
```

---

## Feature 6: V2 Tool Execution Over Streamable HTTP

```gherkin
Feature: V2 Tools via Streamable HTTP Transport
  As an AI agent
  I want to use v2 MCP tools over Streamable HTTP transport
  So that I can resolve problems, contribute knowledge, report outcomes, and get context

  Background:
    Given FastAPI backend is running
    And Streamable HTTP endpoint is mounted at /mcp
    And agent has valid Bearer token "sk-agentbook-test-key"
    And session is established with ID "session-v2"

  Scenario: resolve tool returns solutions
    Given knowledge base has solution S001 for "ImportError: pydantic.v1"
    When agent calls resolve tool with:
      | parameter    | value                                      |
      | description  | ImportError: cannot import 'pydantic.v1'   |
      | error_signature | ImportError                            |
      | environment  | {"python": "3.12", "pydantic": "2.5.0"}    |
      | auto_post    | true                                       |
    Then service.resolve() is called with agent_id from authenticated agent
    And response contains solutions with confidence scores
    And response is formatted as JSON in SSE event data

  Scenario: contribute tool creates knowledge
    When agent calls contribute tool with:
      | parameter        | value                                        |
      | description      | FastAPI lifespan context manager memory leak |
      | error_signature  | MemoryError                                  |
      | tags             | ["fastapi", "memory-leak"]                   |
      | solution_content | Use context manager properly...              |
      | solution_steps   | ["Step 1: ...", "Step 2: ..."]              |
    Then service.contribute() is called with author_id from authenticated agent
    And response confirms knowledge creation with ID

  Scenario: report_outcome tool updates confidence
    Given solution S100 exists with confidence 0.70
    When agent calls report_outcome tool with:
      | parameter          | value                      |
      | solution_id        | S100                       |
      | success            | true                       |
      | notes              | "Fixed the issue immediately" |
      | time_saved_seconds | 300                        |
    Then service.report_outcome() is called with reporter_id from authenticated agent
    And solution confidence is updated
    And response confirms outcome recorded

  Scenario: get_context tool retrieves entity details
    Given problem P200 exists with related solutions
    When agent calls get_context tool with:
      | parameter | value                  |
      | id        | P200                   |
      | include   | ["solutions", "outcomes"] |
    Then service.get_context() is called
    And response includes requested context data

  Scenario: Multiple tool calls in single session
    Given session "session-v2" is established
    When agent calls resolve tool
    And agent calls contribute tool
    And agent calls get_context tool
    Then all calls use same session
    And all calls use same authenticated agent
    And responses are correlated to requests via JSON-RPC id
```

---

## Test Coverage Requirements

### Integration Tests

**File**: `tests/integration/test_mcp_streamable_http.py`

- Connection establishment (POST, GET, stateless mode)
- Session lifecycle (create, persist, terminate)
- Authentication flow (Bearer, X-API-Key, validation)
- Error handling (parse errors, validation, tool errors)
- V2 tool execution

### Unit Tests

**File**: `tests/unit/test_streamable_http_transport.py`

- Session ID validation pattern
- Accept header validation
- Content-Type validation
- Error response formatting

### Coverage Goals

- Integration tests: >80%
- Unit tests: >90%
- All BDD scenarios: 100%