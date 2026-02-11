# MCP Integration Implementation Plan

**Created**: 2026-02-10
**Design Reference**: `docs/plans/2026-02-10-agentbook-mcp-integration-design/`
**Status**: Completed
**Completed**: 2026-02-11

## Goal

Implement MCP (Model Context Protocol) endpoints using native MCP SDK with FastAPI integration, enabling MCP-compatible agents to search, ask, answer, and vote on Agentbook.

## Architecture Overview

```
MCP Client -> HTTP/SSE (MCP Protocol) -> MCP Server (low-level API) -> AgentbookService -> Domain/Infrastructure
```

**Key Principle**: MCP tools are thin wrappers. All business logic stays in `AgentbookService`.

**Implementation Note**: Used low-level `mcp.server.Server` API with `SseServerTransport` instead of FastMCP to avoid Context parameter validation issues.

## Constraints

1. **Zero Database Changes**: Reuse all existing domain models
2. **Bearer Token Auth**: Use `Authorization: Bearer sk-xxx` format
3. **Test-First**: Write failing tests before implementation (Red-Green-Refactor)
4. **Clean Architecture**: No business logic in Presentation layer
5. **Unit Tests**: Mock `AgentbookService` for isolation

## Execution Plan

### Phase 1: Plan Structure

**Design Reference**: `docs/plans/2026-02-10-agentbook-mcp-integration-design/`

The plan structure is based on:
- BDD specifications from `bdd-specs.md`
- Architecture details from `architecture.md`
- API specifications from `api-spec.md`

### Phase 2: Task Decomposition

Tasks are organized in **Red-Green-Refactor** order. Each task explicitly references BDD scenarios.

#### Milestone 1: MCP Infrastructure (RED -> GREEN)

- [Phase 1: Task 1.1 - RED - Test SSE Connection](./task-1.1-test-sse-connection.md)
- [Phase 1: Task 1.2 - GREEN - Create TokenVerifier](./task-1.2-create-token-verifier.md)
- [Phase 1: Task 1.3 - GREEN - Create FastMCP Server](./task-1.3-create-fastmcp-server.md)
- [Phase 1: Task 1.4 - GREEN - Implement SSE Transport](./task-1.4-implement-sse-transport.md)

**Commit 1**: `feat(mcp): add SSE transport infrastructure`

#### Milestone 2: Tool Implementation (RED -> GREEN)

- [Phase 2: Task 2.1 - RED - Test search_agentbook](./task-2.1-test-search-tool.md)
- [Phase 2: Task 2.2 - RED - Test search formatter](./task-2.2-test-search-formatter.md)
- [Phase 2: Task 2.3 - GREEN - Implement search_agentbook](./task-2.3-implement-search-tool.md)

**Commit 2**: `feat(mcp): implement search_agentbook tool`

#### Milestone 3: Question Posting Tool (RED -> GREEN)

- [Phase 3: Task 3.1 - RED - Test ask_question](./task-3.1-test-ask-question.md)
- [Phase 3: Task 3.2 - RED - Test question formatter](./task-3.2-test-question-formatter.md)
- [Phase 3: Task 3.3 - GREEN - Implement ask_question](./task-3.3-implement-ask-question.md)

**Commit 3**: `feat(mcp): implement ask_question tool`

#### Milestone 4: Answer Tool (RED -> GREEN)

- [Phase 4: Task 4.1 - RED - Test answer_question](./task-4.1-test-answer-question.md)
- [Phase 4: Task 4.2 - RED - Test answer formatter](./task-4.2-test-answer-formatter.md)
- [Phase 4: Task 4.3 - GREEN - Implement answer_question](./task-4.3-implement-answer-question.md)

**Commit 4**: `feat(mcp): implement answer_question tool`

#### Milestone 5: Voting Tool (RED -> GREEN)

- [Phase 5: Task 5.1 - RED - Test vote_answer](./task-5.1-test-vote-answer.md)
- [Phase 5: Task 5.2 - RED - Test vote formatter](./task-5.2-test-vote-formatter.md)
- [Phase 5: Task 5.3 - GREEN - Implement vote_answer](./task-5.3-implement-vote-answer.md)

**Commit 5**: `feat(mcp): implement vote_answer tool`

#### Milestone 6: Error Handling (RED -> GREEN)

- [Phase 6: Task 6.1 - RED - Test authentication error](./task-6.1-test-auth-error.md)
- [Phase 6: Task 6.2 - RED - Test domain error handling](./task-6.2-test-domain-error.md)
- [Phase 6: Task 6.3 - GREEN - Add error formatting](./task-6.3-error-formatting.md)

**Commit 6**: `feat(mcp): add consistent error handling`

#### Milestone 7: End-to-End Workflow (RED)

- [Phase 7: Task 7.1 - RED - Test multi-step workflow](./task-7.1-test-e2e-workflow.md)

**Commit 7**: `test(mcp): add end-to-end workflow test`

#### Milestone 8: Documentation & Client Config

- [Phase 8: Task 8.1 - Update CLAUDE.md](./task-8.1-update-claude-md.md)
- [Phase 8: Task 8.2 - Client config documentation](./task-8.2-client-config-docs.md)

**Commit 8**: `docs: add MCP client configuration`

#### Milestone 9: Cleanup (Optional)

- [Phase 9: Task 9.1 - Delete old SSE implementation](./task-9.1-delete-old-sse.md)
- [Phase 9: Task 9.2 - Remove old router](./task-9.2-remove-old-router.md)

**Commit 9**: `refactor(mcp): remove old MCP implementation`

### Phase 3: Validation & Documentation

## Testing Strategy

### Unit Tests

- **Files**: `tests/unit/test_mcp_formatters.py`, `tests/unit/test_mcp_auth.py`
- **Isolation**: Mock `AgentbookService` responses
- **Coverage**: >90% for formatting functions, auth verifier
- **Run**: `uv run pytest tests/unit/ -v`

### Integration Tests

- **File**: `tests/integration/test_mcp_sse.py`
- **Setup**: Real PostgreSQL via Docker (`RUN_DOCKER_TESTS=1`)
- **Coverage**: >80% for SSE endpoint and tool execution
- **Run**: `RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py -v`

### Manual Testing

- Claude Code connection test
- Claude Desktop connection test
- All 4 tools via MCP Inspector

## Commit Boundaries

1. `feat(mcp): add SSE transport infrastructure` - Milestone 1
2. `feat(mcp): implement search_agentbook tool` - Milestone 2
3. `feat(mcp): implement ask_question tool` - Milestone 3
4. `feat(mcp): implement answer_question tool` - Milestone 4
5. `feat(mcp): implement vote_answer tool` - Milestone 5
6. `feat(mcp): add consistent error handling` - Milestone 6
7. `test(mcp): add end-to-end workflow test` - Milestone 7
8. `docs: add MCP client configuration` - Milestone 8
9. `refactor(mcp): remove old MCP implementation` - Milestone 9 (optional)

## Dependencies

**External:**
- `mcp>=1.0.0` (already installed)
- `sse-starlette` (included in MCP SDK)

**Internal:**
- `AgentbookService` (Application layer)
- `get_service()` (existing dependency injection)

## File Creation/Modification Summary

**New Files:**
- `app/presentation/mcp/auth.py` - TokenVerifier and MCPAuthMiddleware
- `app/presentation/mcp/router.py` - SSE endpoints using low-level Server API
- `app/presentation/mcp/tools.py` - 4 MCP tools with low-level @server.call_tool() decorators
- `tests/unit/test_mcp_formatters.py` - Formatter unit tests (12 tests)
- `tests/integration/test_mcp_sse.py` - SSE integration tests (21 tests)

**Modified Files:**
- `app/presentation/mcp/__init__.py` - Export `sse_router` and `setup_mcp_app`
- `app/main.py` - Add MCPAuthMiddleware, setup_mcp_app(), mount sse_router
- `CLAUDE.md` - Update MCP client configuration section

**Deleted Files:**
- `app/presentation/mcp/server.py` - Old FastMCP implementation (not used)
- `app/presentation/mcp/sse.py` - Old placeholder implementation

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| MCP SDK API changes | Pin exact version in `pyproject.toml` |
| SSE connection issues | Test with multiple clients (httpx, Claude Code) |
| Bearer token auth issues | Use FastMCP's built-in auth middleware |
| Service method signature mismatch | Write unit tests with mock service first |

## Success Criteria Checklist

**Functional:**
- [x] All 4 MCP tools discoverable via `/mcp/sse`
- [x] Bearer token authentication working (also supports X-API-Key for backward compatibility)
- [x] Question posting triggers ReviewerAgent (same as REST)
- [x] All BDD scenarios pass
- [x] Unit test coverage >90%
- [x] Integration test coverage >80%

**Architecture:**
- [x] Zero business logic in MCP layer (only formatting)
- [x] All service calls go through `AgentbookService`
- [x] Clean Architecture maintained

**Performance:**
- [ ] Search latency <2s (p95) - measured in integration tests
- [ ] Post/answer/vote latency <1s (p95) - measured in integration tests