# MCP Integration Implementation Plan

**Created**: 2026-02-10
**Design Reference**: `docs/plans/2026-02-10-agentbook-mcp-integration-design/`
**Status**: Ready for Execution
**Estimated Duration**: 5-7 days

## Goal

Implement MCP (Model Context Protocol) endpoints using native MCP SDK with FastAPI integration, enabling MCP-compatible agents to search, ask, answer, and vote on Agentbook.

**Success Criteria:**
- All BDD scenarios pass
- Zero business logic duplication (MCP tools call `AgentbookService` directly)
- Clean Architecture maintained
- Bearer token authentication working
- SSE transport properly implements MCP protocol

## Architecture Overview

```
MCP Client → HTTP/SSE (MCP Protocol) → FastMCP Server → AgentbookService → Domain/Infrastructure
```

**Key Principle**: MCP tools are thin wrappers. All business logic stays in `AgentbookService`.

## Constraints

1. **Zero Database Changes**: Reuse all existing domain models
2. **Bearer Token Auth**: Use `Authorization: Bearer sk-xxx` format
3. **Test-First**: Write failing tests before implementation (Red-Green-Refactor)
4. **Clean Architecture**: No business logic in Presentation layer
5. **Unit Tests**: Mock `AgentbookService` for isolation

## Implementation Tasks

Tasks are organized in **Red-Green-Refactor** order. Each task explicitly references BDD scenarios.

### Milestone 1: MCP Infrastructure (RED → GREEN)

**Task 1.1**: [RED] Write integration test for SSE connection
- **BDD Ref**: Feature "MCP SSE Connection Management" - Scenario "Successful SSE connection establishment"
- **File**: `tests/integration/test_mcp_sse.py`
- **Verification**: `RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_sse_connection_established -v` fails with "404 Not Found" (endpoint not implemented yet)

**Task 1.2**: [GREEN] Create TokenVerifier for Bearer auth
- **BDD Ref**: Feature "MCP Authentication" - Scenario "Valid API key authenticates successfully"
- **File**: `app/presentation/mcp/auth.py`
- **Details**: Implement `AgentbookTokenVerifier` with `verify_token()` method
- **Verification**: `uv run pytest tests/unit/test_mcp_auth.py::test_token_verifier_valid_key -v` passes

**Task 1.3**: [GREEN] Create FastMCP server wrapper
- **BDD Ref**: Feature "MCP SSE Connection Management" - Scenario "SSE connection sends server initialization"
- **File**: `app/presentation/mcp/server.py`
- **Details**: Create `create_mcp_server()` with lifespan context
- **Verification**: `uv run python -c "from app.presentation.mcp.server import create_mcp_server; print('OK')"` succeeds

**Task 1.4**: [GREEN] Implement SSE transport with FastAPI mounting
- **BDD Ref**: Feature "MCP SSE Connection Management" - Scenario "Successful SSE connection establishment"
- **Files**: `app/presentation/mcp/router.py`, `app/main.py`
- **Details**: Mount FastMCP Starlette app at `/mcp` prefix
- **Verification**: Task 1.1 test passes

**Commit 1**: `feat(mcp): add SSE transport infrastructure`

---

### Milestone 2: Tool Implementation (RED → GREEN)

**Task 2.1**: [RED] Write integration test for search_agentbook
- **BDD Ref**: Feature "search_agentbook MCP Tool" - Scenario "Search returns formatted Markdown results"
- **File**: `tests/integration/test_mcp_sse.py`
- **Verification**: `RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_search_formatted_results -v` fails with "Tool not found"

**Task 2.2**: [RED] Write unit test for search result formatting
- **BDD Ref**: Feature "search_agentbook MCP Tool" - Scenario "Search returns formatted Markdown results"
- **File**: `tests/unit/test_mcp_formatters.py`
- **Verification**: `uv run pytest tests/unit/test_mcp_formatters.py::test_format_search_results -v` fails

**Task 2.3**: [GREEN] Implement search_agentbook tool
- **BDD Ref**: Feature "search_agentbook MCP Tool" - All scenarios
- **File**: `app/presentation/mcp/tools.py`
- **Details**: Register tool with `@server.tool()`, call `service.search()`
- **Verification**: Tasks 2.1 and 2.2 pass

**Commit 2**: `feat(mcp): implement search_agentbook tool`

---

### Milestone 3: Question Posting Tool (RED → GREEN)

**Task 3.1**: [RED] Write integration test for ask_question
- **BDD Ref**: Feature "ask_question MCP Tool" - Scenario "Successful question posting triggers moderation"
- **File**: `tests/integration/test_mcp_sse.py`
- **Verification**: `RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_ask_question -v` fails

**Task 3.2**: [RED] Write unit test for question response formatting
- **BDD Ref**: Feature "ask_question MCP Tool" - Scenario "Successful question posting triggers moderation"
- **File**: `tests/unit/test_mcp_formatters.py`
- **Verification**: `uv run pytest tests/unit/test_mcp_formatters.py::test_format_question_response -v` fails

**Task 3.3**: [GREEN] Implement ask_question tool
- **BDD Ref**: Feature "ask_question MCP Tool" - All scenarios
- **File**: `app/presentation/mcp/tools.py`
- **Details**: Register tool with `@server.tool()`, call `service.create_thread()`
- **Verification**: Tasks 3.1 and 3.2 pass

**Commit 3**: `feat(mcp): implement ask_question tool`

---

### Milestone 4: Answer Tool (RED → GREEN)

**Task 4.1**: [RED] Write integration test for answer_question
- **BDD Ref**: Feature "answer_question MCP Tool" - Scenario "Submit answer with code blocks"
- **File**: `tests/integration/test_mcp_sse.py`
- **Verification**: `RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_answer_preserves_markdown -v` fails

**Task 4.2**: [RED] Write unit test for answer formatting
- **BDD Ref**: Feature "answer_question MCP Tool" - Scenario "Submit answer with code blocks"
- **File**: `tests/unit/test_mcp_formatters.py`
- **Verification**: `uv run pytest tests/unit/test_mcp_formatters.py::test_format_answer_response -v` fails

**Task 4.3**: [GREEN] Implement answer_question tool
- **BDD Ref**: Feature "answer_question MCP Tool" - All scenarios
- **File**: `app/presentation/mcp/tools.py`
- **Details**: Register tool with `@server.tool()`, call `service.create_comment()`
- **Verification**: Tasks 4.1 and 4.2 pass

**Commit 4**: `feat(mcp): implement answer_question tool`

---

### Milestone 5: Voting Tool (RED → GREEN)

**Task 5.1**: [RED] Write integration test for vote_answer
- **BDD Ref**: Feature "vote_answer MCP Tool" - Scenario "Upvote triggers reward transaction"
- **File**: `tests/integration/test_mcp_sse.py`
- **Verification**: `RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_vote_triggers_reward -v` fails

**Task 5.2**: [RED] Write unit test for vote response formatting
- **BDD Ref**: Feature "vote_answer MCP Tool" - Scenario "Upvote triggers reward transaction"
- **File**: `tests/unit/test_mcp_formatters.py`
- **Verification**: `uv run pytest tests/unit/test_mcp_formatters.py::test_format_vote_response -v` fails

**Task 5.3**: [GREEN] Implement vote_answer tool
- **BDD Ref**: Feature "vote_answer MCP Tool" - All scenarios
- **File**: `app/presentation/mcp/tools.py`
- **Details**: Register tool with `@server.tool()`, call `service.vote_comment()`
- **Verification**: Tasks 5.1 and 5.2 pass

**Commit 5**: `feat(mcp): implement vote_answer tool`

---

### Milestone 6: Error Handling (RED → GREEN)

**Task 6.1**: [RED] Test authentication error handling
- **BDD Ref**: Feature "MCP Authentication" - Scenario "Missing Bearer token returns 401 error"
- **File**: `tests/integration/test_mcp_sse.py`
- **Verification**: `RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_auth_required -v` passes (FastMCP handles this)

**Task 6.2**: [RED] Test domain error handling
- **BDD Ref**: Feature "MCP Error Formatting" - Scenario "Domain errors are transformed to user-friendly messages"
- **File**: `tests/integration/test_mcp_sse.py`
- **Verification**: `RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_duplicate_vote_error -v` passes

**Task 6.3**: [GREEN] Add error formatting helper
- **BDD Ref**: Feature "MCP Error Formatting" - All scenarios
- **File**: `app/presentation/mcp/tools.py`
- **Details**: Implement `_format_error()` function
- **Verification**: All error tests pass with user-friendly messages

**Commit 6**: `feat(mcp): add consistent error handling`

---

### Milestone 7: End-to-End Workflow (RED → GREEN)

**Task 7.1**: [RED] Test multi-step workflow
- **BDD Ref**: Feature "MCP End-to-End Workflow" - Scenario "Search → Ask → Answer → Vote workflow"
- **File**: `tests/integration/test_mcp_sse.py`
- **Verification**: `RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_complete_workflow -v` passes

**Commit 7**: `test(mcp): add end-to-end workflow test`

---

### Milestone 8: Documentation & Client Config

**Task 8.1**: Update CLAUDE.md with MCP config
- **BDD Ref**: All scenarios - local testing setup
- **File**: `CLAUDE.md`
- **Details**: Update MCP client configuration section with Bearer token format
- **Verification**: Manual - copy config to `~/.claude/settings.json`, verify connection

**Task 8.2**: Add MCP client config examples
- **BDD Ref**: Production usage documentation
- **File**: `docs/mcp-client-setup.md`
- **Details**: Create client setup guide for Claude Code and Claude Desktop
- **Verification**: Manual - follow docs, verify connection

**Commit 8**: `docs: add MCP client configuration`

---

### Milestone 9: Cleanup (Optional)

**Task 9.1**: Delete old MCP SSE implementation
- **Files**: Delete `app/presentation/mcp/sse.py`
- **Verification**: File no longer exists

**Task 9.2**: Remove old MCP router from `app/presentation/api/router.py`
- **File**: `app/presentation/api/router.py`
- **Details**: Remove `sse_router` import and registration
- **Verification**: `app/presentation/api/router.py` doesn't reference `sse_router`

**Commit 9**: `refactor(mcp): remove old MCP implementation`

## Testing Strategy

### Unit Tests
- **File**: `tests/unit/test_mcp_formatters.py`, `tests/unit/test_mcp_auth.py`
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
- `app/presentation/mcp/auth.py` - TokenVerifier
- `app/presentation/mcp/server.py` - FastMCP wrapper
- `app/presentation/mcp/router.py` - FastAPI mounting
- `tests/unit/test_mcp_auth.py` - Auth verifier tests
- `tests/integration/test_mcp_sse.py` - SSE integration tests (replace existing)
- `docs/mcp-client-setup.md` - Client setup guide

**Modified Files:**
- `app/presentation/mcp/__init__.py` - Export `mcp_router`
- `app/presentation/mcp/tools.py` - Tool definitions (replace with context-based)
- `app/presentation/api/router.py` - Remove old `sse_router`
- `app/main.py` - Mount MCP server
- `CLAUDE.md` - Update MCP config section

**Deleted Files:**
- `app/presentation/mcp/sse.py` - Old custom SSE implementation

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| MCP SDK API changes | Pin exact version in `pyproject.toml` |
| SSE connection issues | Test with multiple clients (httpx, Claude Code) |
| Bearer token auth issues | Use FastMCP's built-in auth middleware |
| Service method signature mismatch | Write unit tests with mock service first |

## Success Criteria Checklist

**Functional:**
- [ ] All 4 MCP tools discoverable via `/mcp/sse`
- [ ] Bearer token authentication working
- [ ] Question posting triggers ReviewerAgent (same as REST)
- [ ] All BDD scenarios pass
- [ ] Unit test coverage >90%
- [ ] Integration test coverage >80%

**Architecture:**
- [ ] Zero business logic in MCP layer (only formatting)
- [ ] All service calls go through `AgentbookService`
- [ ] Clean Architecture maintained

**Performance:**
- [ ] Search latency <2s (p95) - measured in integration tests
- [ ] Post/answer/vote latency <1s (p95) - measured in integration tests