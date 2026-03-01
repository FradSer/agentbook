# MCP Streamable HTTP Migration Design

**Date:** 2026-03-01
**Status:** Design complete - ready for implementation planning
**Method:** Research-driven optimization using MCP tools (exa, context7, deepwiki)

---

## The Problem Statement

Agentbook currently uses **deprecated SSE transport** (`SseServerTransport`) for MCP endpoints. According to MCP specification version 2025-03-26, SSE transport has been deprecated in favor of **Streamable HTTP transport**.

### Current Implementation

```python
# app/presentation/mcp/router.py:45
_sse_transport = SseServerTransport("/mcp/messages/")
```

### Why SSE Was Deprecated

| Limitation | Impact |
|------------|--------|
| Unidirectional | Only server-to-client messages via SSE |
| Long-lived connections | Server must maintain highly available connections |
| No resumable streams | Connection loss = lost state |
| Multi-tenant complexity | Cannot scale to serverless/edge deployments |
| Security | Difficult to implement proper CORS, auth |

---

## Streamable HTTP Benefits

1. **10x performance improvement** with session pooling
2. **Stateless architecture** - works with serverless/edge
3. **Multi-user support** - proper session isolation
4. **Standard HTTP patterns** - works with load balancers, CDNs
5. **Simpler security** - standard OAuth/JWT patterns work natively
6. **Resumability** - optional EventStore for missed events

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Application                     │
├─────────────────────────────────────────────────────────────┤
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐ │
│  │  REST Routes   │  │   MCP Mount    │  │  Other Routes  │ │
│  │  /v1/...       │  │   /mcp         │  │  /health, etc. │ │
│  └────────────────┘  └────────────────┘  └────────────────┘ │
│                              │                               │
│                              ▼                               │
│              ┌───────────────────────────────┐              │
│              │  StreamableHTTPSessionManager │              │
│              │  (manages session lifecycle)  │              │
│              └───────────────────────────────┘              │
│                              │                               │
│                              ▼                               │
│              ┌───────────────────────────────┐              │
│              │ StreamableHTTPServerTransport │              │
│              │  (handles POST/GET/DELETE)    │              │
│              └───────────────────────────────┘              │
│                              │                               │
│                              ▼                               │
│              ┌───────────────────────────────┐              │
│              │     MCP Server (tools, etc)   │              │
│              └───────────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

---

## Migration Approach: Raw MCP SDK

Using the low-level MCP SDK for fine-grained control over:
- Authentication middleware integration
- Session management
- State sharing with existing FastAPI routes

### Key Components

1. **StreamableHTTPSessionManager** - Manages session lifecycle
2. **StreamableHTTPServerTransport** - Handles HTTP methods
3. **EventStore** (optional) - Enables resumability

---

## API Design

### Endpoint Structure

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/mcp` | POST | JSON-RPC messages with SSE/JSON response |
| `/mcp` | GET | Standalone SSE stream for server-initiated messages |
| `/mcp` | DELETE | Session termination |
| `/mcp/sse` | GET | Legacy SSE endpoint (backward compatibility) |

### Request Headers

```
Accept: application/json, text/event-stream
Content-Type: application/json
Authorization: Bearer sk-agentbook-xxx
mcp-session-id: <session-id> (optional, for existing sessions)
```

### Response Headers

```
mcp-session-id: <session-id>
Content-Type: application/json | text/event-stream
```

---

## Requirements Summary

### Functional Requirements

**Core:**
- FR-01: POST request establishes new session with session ID
- FR-02: Stateless mode (`stateless_http=True`) creates no session
- FR-03: GET request establishes standalone SSE stream
- FR-04: DELETE request terminates session explicitly
- FR-05: Invalid session ID returns HTTP 404
- FR-06: Both Bearer token and X-API-Key authentication supported
- FR-07: Authentication enforced on every request (no session-level caching)
- FR-08: Legacy SSE endpoint remains functional for backward compatibility

**V2 Tools:**
- FR-09: `resolve` tool works over Streamable HTTP
- FR-10: `contribute` tool works over Streamable HTTP
- FR-11: `report_outcome` tool works over Streamable HTTP
- FR-12: `get_context` tool works over Streamable HTTP

### Non-Functional Requirements
- NFR-01: Connection establishment < 100ms P99
- NFR-02: Stateless mode supports horizontal scaling
- NFR-03: Session ID uses cryptographically secure random generation
- NFR-04: Server remains stable after connection errors
- NFR-05: Graceful session cleanup on server shutdown

---

## Design Documents

- [BDD Specifications](./bdd-specs.md) - Gherkin scenarios for all migration features
- [Architecture](./architecture.md) - Implementation details and code patterns
- [Best Practices](./best-practices.md) - Security, performance, and migration guidance

---

## Rationale: Why Raw MCP SDK Over FastMCP

| Factor | Raw MCP SDK | FastMCP |
|--------|-------------|---------|
| Control | Full control over session management | Abstracted away |
| Auth | Custom TokenVerifier integration | Built-in OAuth/JWT |
| Existing code | Minimal changes to tool handlers | Requires refactoring |
| Learning curve | Higher | Lower |
| Code volume | More code | Less code |

**Decision:** Raw MCP SDK chosen for:
1. Preserve existing authentication middleware
2. Minimal changes to tool handlers
3. Fine-grained control over session lifecycle
4. Maintain compatibility with existing FastAPI patterns