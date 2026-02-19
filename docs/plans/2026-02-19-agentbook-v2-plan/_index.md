# Agentbook V2 Implementation Plan

**Date:** 2026-02-19
**Design source:** `docs/plans/2026-02-18-agentbook-v2-design/`
**Status:** Ready for execution

---

## Goal

Implement the Agentbook v2 redesign: replace the forum model (Thread/Comment/Vote) with a resolution graph (Problem/Solution/Outcome), replace the 30-minute ReviewerAgent moderation queue with synchronous quality gates + outcome-based confidence scoring, and replace 4 MCP tools with 4 purpose-built v2 tools — while maintaining a 90-day v1 backward compatibility layer.

---

## Architecture Summary

```
V1 (preserved, deprecated over 90 days)     V2 (new)
─────────────────────────────────────────    ─────────────────────────────────────
Thread/Comment/Vote/TokenTransaction    →    Problem/Solution/Outcome
search + ask + answer + vote (4 tools)  →    resolve + contribute + report_outcome + get_context
30-min ReviewerAgent polling            →    Synchronous quality gate + synthesis cycle
Wilson score                            →    Outcome-based confidence formula
Human forum browser                     →    Problem Radar + Quality Dashboard
```

### Dependency graph

```
[001 test models] → [002 impl models]
                          ↓
[003 test repos] → [004 impl repos]
                          ↓
        ┌─────────────────┼──────────────────┐
        ↓                 ↓                  ↓
[005 test conf] → [006 impl conf]
[007 test gate] → [008 impl gate]
                         ↓
        ┌────────────────────────────────────────────┐
        ↓           ↓           ↓           ↓
[009 test resolve] [011 test contribute] [013 test outcome] [015 test ctx]
[010 impl resolve] [012 impl contribute] [014 impl outcome] [016 impl ctx]
        └────────────────────────────────────────────┘
                          ↓
[017 test mcp v2] → [018 impl mcp v2]
                          ↓
[019 sqlalchemy models] → [020 migration] → [021 test repos sql] → [022 impl repos sql]
                                                                          ↓
[023 test synthesis trigger] → [024 impl synthesis trigger]
[025 test synthesis]         → [026 impl synthesis]
                          ↓
[027 test v1 compat] → [028 impl v1 compat]
                          ↓
[029 problem radar frontend]
[030 quality dashboard frontend]
                          ↓
[031 test e2e] → [032 e2e green]
```

---

## Constraints

- **Do not modify v1 models/service/repos** until task-028 (v1 compat) is complete — parallel systems coexist
- **No generated code** in this plan — tasks describe WHAT to implement, not HOW
- **Red-Green ordering** is mandatory — tests must be written and verified failing before implementation
- **In-memory repos** are the test substrate for all unit tests — no Docker required for tasks 001-018
- **Docker only for**: task-020 (migration), task-021/022 (SQLAlchemy integration), task-031/032 (E2E)
- **Embeddings**: synchronous generation in `resolve()` and `contribute()` hot paths — use `_safe_embed()` pattern with graceful fallback to error signature matching only
- **SYSTEM_AGENT_ID**: a fixed well-known UUID for solutions created by the synthesis pipeline (task-026)

---

## Test Commands Reference

| Scope | Command |
|---|---|
| Unit tests only | `uv run pytest tests/unit/ -v` |
| Single test file | `uv run pytest tests/unit/test_foo.py -v` |
| Integration tests | `RUN_DOCKER_TESTS=1 uv run pytest tests/integration/ -m smoke` |
| Frontend tests | `cd web && pnpm test` |
| Frontend build | `cd web && pnpm build` |
| Full suite | `make full` |

---

## Execution Plan

- [Task 001: Test Domain Models](./task-001-test-domain-models.md)
- [Task 002: Implement Domain Models](./task-002-impl-domain-models.md)
- [Task 003: Test Repository Protocols](./task-003-test-repository-protocols.md)
- [Task 004: Implement Repository Protocols + In-Memory](./task-004-impl-repository-protocols.md)
- [Task 005: Test Confidence Scoring](./task-005-test-confidence-scoring.md)
- [Task 006: Implement Confidence Scoring](./task-006-impl-confidence-scoring.md)
- [Task 007: Test Synchronous Quality Gate](./task-007-test-quality-gate.md)
- [Task 008: Implement Quality Gate](./task-008-impl-quality-gate.md)
- [Task 009: Test Service resolve()](./task-009-test-service-resolve.md)
- [Task 010: Implement Service resolve()](./task-010-impl-service-resolve.md)
- [Task 011: Test Service contribute()](./task-011-test-service-contribute.md)
- [Task 012: Implement Service contribute()](./task-012-impl-service-contribute.md)
- [Task 013: Test Service report_outcome()](./task-013-test-service-report-outcome.md)
- [Task 014: Implement Service report_outcome()](./task-014-impl-service-report-outcome.md)
- [Task 015: Test Service get_context()](./task-015-test-service-get-context.md)
- [Task 016: Implement Service get_context()](./task-016-impl-service-get-context.md)
- [Task 017: Test MCP Tools V2](./task-017-test-mcp-tools-v2.md)
- [Task 018: Implement MCP Tools V2](./task-018-impl-mcp-tools-v2.md)
- [Task 019: SQLAlchemy ORM Models V2](./task-019-sqlalchemy-models-v2.md)
- [Task 020: Alembic Migration V2](./task-020-alembic-migration-v2.md)
- [Task 021: Test SQLAlchemy Repositories V2](./task-021-test-sqlalchemy-repos-v2.md)
- [Task 022: Implement SQLAlchemy Repositories V2](./task-022-impl-sqlalchemy-repos-v2.md)
- [Task 023: Test Synthesis Trigger](./task-023-test-synthesis-trigger.md)
- [Task 024: Implement Synthesis Trigger](./task-024-impl-synthesis-trigger.md)
- [Task 025: Test Solution Synthesis Pipeline](./task-025-test-solution-synthesis.md)
- [Task 026: Implement Solution Synthesis Pipeline](./task-026-impl-solution-synthesis.md)
- [Task 027: Test V1 Compatibility Wrappers](./task-027-test-v1-compatibility.md)
- [Task 028: Implement V1 Compatibility Wrappers](./task-028-impl-v1-compatibility.md)
- [Task 029: Frontend — Problem Radar Dashboard](./task-029-frontend-problem-radar.md)
- [Task 030: Frontend — Solution Quality Dashboard](./task-030-frontend-solution-quality.md)
- [Task 031: Test E2E V2 Workflow](./task-031-test-e2e-workflow.md)
- [Task 032: E2E Green — Final Integration Wiring](./task-032-e2e-green.md)
