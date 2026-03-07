# MCP Streamable HTTP Migration Plan

**Date:** 2026-03-01
**Status:** Ready for execution
**Design:** [docs/plans/2026-03-01-mcp-streamable-http-migration-design/](../2026-03-01-mcp-streamable-http-migration-design/)

---

## Goal

Migrate from deprecated SSE transport to Streamable HTTP transport for MCP endpoints, enabling:
- 10x performance improvement with session pooling
- Stateless architecture for horizontal scaling
- Backward compatibility during migration

---

## Architecture Constraints

1. **Clean Architecture**: MCP presentation layer uses service layer (no infrastructure imports)
2. **BDD Workflow**: Test-first (Red-Green) for all features
3. **Backward Compatibility**: SSE endpoint must remain functional during migration
4. **Configuration Toggle**: `mcp_transport` setting controls which transports are mounted

---

## Execution Plan

### Phase 1: Configuration

- [Task 001: Add MCP Transport Configuration](./task-001-config-mcp-transport.md) - Add settings for transport selection

### Phase 2: Session Validation

- [Task 002: Session ID Validation Test](./task-002-session-validation-test.md) - Unit tests for session ID
- [Task 002: Session ID Validation Implementation](./task-002-session-validation-impl.md) - Cryptographic session ID generation

### Phase 3: Streamable HTTP Router

- [Task 003: Streamable HTTP Router Test](./task-003-streamable-router-test.md) - Integration tests for endpoint
- [Task 003: Streamable HTTP Router Implementation](./task-003-streamable-router-impl.md) - Create streamable_router.py

### Phase 4: Authentication Integration

- [Task 004: Authentication Integration Test](./task-004-authentication-test.md) - Auth flow tests
- [Task 004: Authentication Integration Implementation](./task-004-authentication-impl.md) - Integrate TokenVerifier

### Phase 5: Backward Compatibility

- [Task 005: Backward Compatibility Test](./task-005-backward-compat-test.md) - Test both transports
- [Task 005: Backward Compatibility Implementation](./task-005-backward-compat-impl.md) - Config toggle in main.py

### Phase 6: V2 Tools Integration

- [Task 006: V2 Tools Test](./task-006-v2-tools-test.md) - Tool execution tests
- [Task 006: V2 Tools Implementation](./task-006-v2-tools-impl.md) - Verify tool handlers

### Phase 7: Session Management

- [Task 011: Session Management Test](./task-011-session-mgmt-test.md) - Session lifecycle tests
- [Task 011: Session Management Implementation](./task-011-session-mgmt-impl.md) - DELETE, cleanup, validation

### Phase 8: Error Handling

- [Task 007: Error Handling Test](./task-007-error-handling-test.md) - Error scenario tests
- [Task 007: Error Handling Implementation](./task-007-error-handling-impl.md) - JSON-RPC error codes

### Phase 9: Tool Parameter Validation

- [Task 012: Tool Parameter Validation Test](./task-012-tool-validation-test.md) - Validation tests
- [Task 012: Tool Parameter Validation Implementation](./task-012-tool-validation-impl.md) - Parameter validation

### Phase 10: Performance & Documentation

- [Task 008: Performance Test](./task-008-performance-test.md) - Latency benchmarks
- [Task 009: Documentation Update](./task-009-docs-update.md) - Update CLAUDE.md

### Phase 11: End-to-End Validation

- [Task 010: End-to-End Smoke Test](./task-010-e2e-test.md) - Complete workflow tests

---

## Dependency Graph

```
001 (config)
  │
  └─► 002-test ──► 002-impl
                       │
                       └─► 003-test ──► 003-impl
                                         │
                                         ├─► 004-test ──► 004-impl
                                         │                  │
                                         │                  └─► 005-test ──► 005-impl
                                         │                                    │
                                         │                                    └─► 006-test ──► 006-impl
                                         │                                                      │
                                         │                                                      ├─► 011-test ──► 011-impl
                                         │                                                      │                  │
                                         │                                                      │                  └─► 007-test ──► 007-impl
                                         │                                                      │                                    │
                                         │                                                      └─► 012-test ──► 012-impl            │
                                         │                                                                                          │
                                         └─► 011-test (also depends on 003-impl)                                                   │
                                                                                                                                    ├─► 008-test
                                                                                                                                    │
                                                                                                                                    ├─► 009-docs
                                                                                                                                    │
                                                                                                                                    └─► 010-e2e
```

---

## Files Modified

| File | Tasks | Purpose |
|------|-------|---------|
| `app/core/config.py` | 001 | Add MCP transport settings |
| `app/presentation/mcp/session.py` | 002 | Session ID validation |
| `app/presentation/mcp/streamable_router.py` | 003, 004, 007 | Streamable HTTP endpoint |
| `app/main.py` | 005 | Transport mounting |
| `app/presentation/mcp/tools_v2.py` | 006 | Tool handler verification |
| `CLAUDE.md` | 009 | Documentation update |

---

## Files Created

| File | Tasks | Purpose |
|------|-------|---------|
| `tests/unit/test_session_validation.py` | 002 | Session ID unit tests |
| `tests/integration/test_mcp_streamable_http.py` | 003, 004, 005, 006, 007 | Integration tests |
| `tests/performance/test_mcp_latency.py` | 008 | Performance benchmarks |
| `tests/integration/test_mcp_e2e.py` | 010 | End-to-end tests |

---

## Verification Commands

```bash
# Run all MCP tests
uv run pytest tests/unit/test_session_validation.py tests/integration/test_mcp_streamable_http.py tests/integration/test_mcp_e2e.py -v

# Run performance tests
uv run pytest tests/performance/test_mcp_latency.py -v

# Run full test suite
make fast
```

---

## Rollback Plan

If issues arise:
1. Set `MCP_TRANSPORT=sse` in environment
2. Restart server
3. Only SSE endpoint will be mounted
4. Streamable HTTP code remains but is unused

---

## Success Criteria

- [ ] All integration tests pass
- [ ] Performance tests show P99 < 100ms
- [ ] SSE endpoint remains functional
- [ ] Documentation updated
- [ ] No breaking changes for existing clients