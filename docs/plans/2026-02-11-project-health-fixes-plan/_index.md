# Project Health Fixes Implementation Plan

## Overview

This plan implements fixes for 24 issues identified in the project health check, following TDD principles with Red-Green-Refactor workflow.

## Goal

Address all critical, high, medium, and low priority issues across Backend, Agent, Frontend, and Configuration areas.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Implementation Order                      │
├─────────────────────────────────────────────────────────────────┤
│  1. Backend (Critical/High)                                      │
│     └── MCP Auth > Secret Key > Error Logging                   │
│                                                                  │
│  2. Agent (Critical/High)                                        │
│     └── Backoff > Session Mgmt > Tests                          │
│                                                                  │
│  3. Configuration (High/Medium)                                  │
│     └── Ruff > Railway > CORS Warning                           │
│                                                                  │
│  4. Frontend (Medium/Low)                                        │
│     └── Types > A11y Labels > ARIA Live                         │
│                                                                  │
│  5. Cleanup (Low)                                                │
│     └── Dead Code > Final Verification                          │
└─────────────────────────────────────────────────────────────────┘
```

## Constraints

- **TDD Required**: Write failing tests before implementation
- **One Task Per File**: Each task modifies specific files
- **Verification Required**: Each task has explicit verification steps
- **Minimal Dependencies**: Only true technical prerequisites are declared

## Design Reference

- [Design Documents](../2026-02-11-project-health-fixes-design/)

## Execution Plan

### Backend Tasks (Critical/High)

- [Task 001: Write MCP Authentication Tests](./task-001-mcp-auth-tests.md)
- [Task 002: Implement MCP Authentication](./task-002-mcp-auth-impl.md)
- [Task 003: Write Secret Key Validation Tests](./task-003-secret-key-tests.md)
- [Task 004: Implement Secret Key Validation](./task-004-secret-key-impl.md)
- [Task 005: Add Embedding Error Logging](./task-005-embedding-logging.md)

### Agent Tasks (Critical/High)

- [Task 006: Write Agent Backoff Tests](./task-006-agent-backoff-tests.md)
- [Task 007: Implement Agent Backoff](./task-007-agent-backoff-impl.md)
- [Task 008: Write Agent Session Management Tests](./task-008-agent-session-tests.md)
- [Task 009: Implement Agent Session Management](./task-009-agent-session-impl.md)
- [Task 010: Write Agent Content Rules Tests](./task-010-agent-content-tests.md)
- [Task 011: Implement Agent Content Rules Tests](./task-011-agent-content-impl.md)

### Configuration Tasks (High/Medium)

- [Task 012: Add Ruff Configuration](./task-012-ruff-config.md)
- [Task 013: Fix Railway Configuration](./task-013-railway-config.md)
- [Task 014: Add CORS Warning](./task-014-cors-warning.md)

### Frontend Tasks (Medium/Low)

- [Task 015: Add Frontend Type Safety](./task-015-frontend-types.md)
- [Task 016: Write Frontend Form Labels Tests](./task-016-frontend-a11y-tests.md)
- [Task 017: Implement Frontend Form Labels](./task-017-frontend-a11y-impl.md)
- [Task 018: Implement Frontend ARIA Live Regions](./task-018-frontend-aria.md)
- [Task 019: Write Frontend Page Tests](./task-019-frontend-page-tests.md)
- [Task 020: Implement Frontend Page Tests](./task-020-frontend-page-impl.md)

### Cleanup Tasks (Low)

- [Task 021: Remove Dead Code](./task-021-dead-code.md)
- [Task 022: Final Verification](./task-022-verify-all.md)

## Success Criteria

| Criteria | Verification |
|----------|--------------|
| MCP endpoints require authentication | Task 002 tests pass |
| Secret key required in production | Task 004 tests pass |
| Agent recovers with backoff | Task 007 tests pass |
| Sessions properly managed | Task 009 tests pass |
| Code passes ruff linting | Task 012 verification |
| Frontend builds successfully | Task 015-020 verification |
| All tests pass | Task 022 verification |

## Estimated Scope

| Area | Tasks | Files Changed |
|------|-------|---------------|
| Backend | 5 | 5 files |
| Agent | 6 | 4 files + 3 test files |
| Config | 3 | 2 files |
| Frontend | 6 | 6 files + 3 test files |
| Cleanup | 2 | 4 files |
| **Total** | **22** | **24 files** |