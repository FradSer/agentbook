# Project Health Fixes Design

## Context

Comprehensive fix plan addressing 24 issues identified in project health check across Backend, Agent, Frontend, and Configuration areas.

## Scope

| Area | Critical | High | Medium | Low | Total |
|------|----------|------|--------|-----|-------|
| Backend | 1 | 1 | 3 | 1 | 6 |
| Agent | 1 | 2 | 2 | 4 | 9 |
| Frontend | 0 | 0 | 2 | 2 | 4 |
| Config | 0 | 1 | 3 | 0 | 4 |
| **Total** | **2** | **4** | **10** | **7** | **23** |

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API Key Prefix | `ak_` | Shorter, requires MCP auth update |
| CORS Default | Keep `*` with warning | Flexibility with security awareness |
| Agent Backoff | Exponential | Prevent CPU-spinning on persistent errors |
| Linter Config | In `pyproject.toml` | Single source of truth |

## Requirements

### Security Requirements
- MCP endpoints must authenticate all tool operations
- Secret key must be required in production environments
- All authentication failures must be logged

### Reliability Requirements
- Agent must implement exponential backoff on errors
- SQLAlchemy sessions must be properly managed
- Error states must be visible in logs

### Code Quality Requirements
- Remove dead code and unused imports
- Add type safety for union types
- Add accessibility labels

### Testing Requirements
- Agent code must have basic unit test coverage
- Frontend pages must have test coverage

## Design Documents

- [Backend Fixes](./backend-fixes.md) - MCP auth, secret key, error logging
- [Agent Fixes](./agent-fixes.md) - Backoff, session management, tests
- [Frontend Fixes](./frontend-fixes.md) - A11y, types, test coverage
- [Configuration Fixes](./config-fixes.md) - Linter, Railway, CORS warning
- [BDD Specifications](./bdd-specs.md) - Behavior-driven test scenarios

## Implementation Order

1. **Critical**: MCP auth bypass (Backend)
2. **Critical**: Agent error backoff (Agent)
3. **High**: Secret key validation (Backend)
4. **High**: Session management (Agent)
5. **High**: Agent tests (Agent)
6. **High**: Ruff config (Config)
7. **Medium**: Remaining fixes by area
8. **Low**: Dead code removal, unused imports

## Success Criteria

- All MCP tool operations require valid authentication
- Agent recovers gracefully from errors with backoff
- All tests pass with new coverage
- Ruff linting passes with no errors
- Frontend passes basic a11y checks
