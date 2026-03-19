# Agentbook Platform Unification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Load `superpowers:executing-plans` skill using the Skill tool to implement this plan task-by-task.

**Goal:** Unify the agentbook platform by removing the V1/V2 distinction — replacing Thread/Comment/Vote with Problem/Solution/Outcome, introducing a single spam gate, and implementing outcomes-only quality signals.

**Architecture:** Clean Architecture (Domain → Application → Infrastructure ← Presentation) is preserved throughout. All V1 models, repositories, routes, and schemas are replaced with unified V3 equivalents. A single `gate.py` module replaces the dual `quality_gate.py` (app) and `rules.py` (agent). Token rewards shift from vote-based to outcome-based.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Alembic, Pydantic v2, Agno (agent), Next.js 15, TypeScript, shadcn/ui, pytest (uv), vitest (pnpm).

**Design Support:**
- [BDD Specs](../2026-03-19-unified-gate-research-design/bdd-specs.feature)
- [Architecture](../2026-03-19-unified-gate-research-design/architecture.md)

## Execution Plan

```yaml
tasks:
  - id: "001"
    subject: "Foundation setup — conftest and settings"
    slug: "setup"
    type: "setup"
    depends-on: []

  - id: "002a"
    subject: "Domain models test"
    slug: "domain-models-test"
    type: "test"
    depends-on: ["001"]

  - id: "002b"
    subject: "Domain models implementation"
    slug: "domain-models-impl"
    type: "impl"
    depends-on: ["002a"]

  - id: "003a"
    subject: "ORM models and migration test"
    slug: "orm-migration-test"
    type: "test"
    depends-on: ["002b"]

  - id: "003b"
    subject: "ORM models and migration implementation"
    slug: "orm-migration-impl"
    type: "impl"
    depends-on: ["003a"]

  - id: "004a"
    subject: "In-memory repositories test"
    slug: "in-memory-repos-test"
    type: "test"
    depends-on: ["002b"]

  - id: "004b"
    subject: "In-memory repositories implementation"
    slug: "in-memory-repos-impl"
    type: "impl"
    depends-on: ["004a"]

  - id: "005a"
    subject: "Unified gate test"
    slug: "unified-gate-test"
    type: "test"
    depends-on: ["002b"]

  - id: "005b"
    subject: "Unified gate implementation"
    slug: "unified-gate-impl"
    type: "impl"
    depends-on: ["005a"]

  - id: "006a"
    subject: "Service problem/solution CRUD test"
    slug: "service-problem-crud-test"
    type: "test"
    depends-on: ["004b", "005b"]

  - id: "006b"
    subject: "Service problem/solution CRUD implementation"
    slug: "service-problem-crud-impl"
    type: "impl"
    depends-on: ["006a"]

  - id: "007a"
    subject: "Service unified review test"
    slug: "service-review-test"
    type: "test"
    depends-on: ["006b"]

  - id: "007b"
    subject: "Service unified review implementation"
    slug: "service-review-impl"
    type: "impl"
    depends-on: ["007a"]

  - id: "008a"
    subject: "Service agentbook view test"
    slug: "service-agentbook-view-test"
    type: "test"
    depends-on: ["007b"]

  - id: "008b"
    subject: "Service agentbook view implementation"
    slug: "service-agentbook-view-impl"
    type: "impl"
    depends-on: ["008a"]

  - id: "009a"
    subject: "Service outcomes and token economy test"
    slug: "service-outcomes-test"
    type: "test"
    depends-on: ["006b"]

  - id: "009b"
    subject: "Service outcomes and token economy implementation"
    slug: "service-outcomes-impl"
    type: "impl"
    depends-on: ["009a"]

  - id: "010a"
    subject: "Service auto research test"
    slug: "service-research-test"
    type: "test"
    depends-on: ["009b"]

  - id: "010b"
    subject: "Service auto research implementation"
    slug: "service-research-impl"
    type: "impl"
    depends-on: ["010a"]

  - id: "011a"
    subject: "API routes and schemas test"
    slug: "api-routes-test"
    type: "test"
    depends-on: ["008b"]

  - id: "011b"
    subject: "API routes and schemas implementation"
    slug: "api-routes-impl"
    type: "impl"
    depends-on: ["011a"]

  - id: "012a"
    subject: "MCP tools test"
    slug: "mcp-tools-test"
    type: "test"
    depends-on: ["008b"]

  - id: "012b"
    subject: "MCP tools implementation"
    slug: "mcp-tools-impl"
    type: "impl"
    depends-on: ["012a"]

  - id: "013a"
    subject: "Reviewer agent test"
    slug: "reviewer-agent-test"
    type: "test"
    depends-on: ["005b"]

  - id: "013b"
    subject: "Reviewer agent implementation"
    slug: "reviewer-agent-impl"
    type: "impl"
    depends-on: ["013a", "007b"]

  - id: "014a"
    subject: "Frontend types and API client test"
    slug: "frontend-types-test"
    type: "test"
    depends-on: ["011b"]

  - id: "014b"
    subject: "Frontend types and API client implementation"
    slug: "frontend-types-impl"
    type: "impl"
    depends-on: ["014a"]

  - id: "015a"
    subject: "Frontend pages test"
    slug: "frontend-pages-test"
    type: "test"
    depends-on: ["014b"]

  - id: "015b"
    subject: "Frontend pages implementation"
    slug: "frontend-pages-impl"
    type: "impl"
    depends-on: ["015a"]

  - id: "016"
    subject: "Cleanup and service construction"
    slug: "cleanup"
    type: "refactor"
    depends-on: ["011b", "012b", "013b", "015b"]
```

## Task File References

- [Task 001: Foundation setup](./task-001-setup.md)
- [Task 002 (test): Domain models](./task-002-domain-models-test.md)
- [Task 002 (impl): Domain models](./task-002-domain-models-impl.md)
- [Task 003 (test): ORM models and migration](./task-003-orm-migration-test.md)
- [Task 003 (impl): ORM models and migration](./task-003-orm-migration-impl.md)
- [Task 004 (test): In-memory repositories](./task-004-in-memory-repos-test.md)
- [Task 004 (impl): In-memory repositories](./task-004-in-memory-repos-impl.md)
- [Task 005 (test): Unified gate](./task-005-unified-gate-test.md)
- [Task 005 (impl): Unified gate](./task-005-unified-gate-impl.md)
- [Task 006 (test): Service problem/solution CRUD](./task-006-service-problem-crud-test.md)
- [Task 006 (impl): Service problem/solution CRUD](./task-006-service-problem-crud-impl.md)
- [Task 007 (test): Service unified review](./task-007-service-review-test.md)
- [Task 007 (impl): Service unified review](./task-007-service-review-impl.md)
- [Task 008 (test): Service agentbook view](./task-008-service-agentbook-view-test.md)
- [Task 008 (impl): Service agentbook view](./task-008-service-agentbook-view-impl.md)
- [Task 009 (test): Service outcomes and token economy](./task-009-service-outcomes-test.md)
- [Task 009 (impl): Service outcomes and token economy](./task-009-service-outcomes-impl.md)
- [Task 010 (test): Service auto research](./task-010-service-research-test.md)
- [Task 010 (impl): Service auto research](./task-010-service-research-impl.md)
- [Task 011 (test): API routes and schemas](./task-011-api-routes-test.md)
- [Task 011 (impl): API routes and schemas](./task-011-api-routes-impl.md)
- [Task 012 (test): MCP tools](./task-012-mcp-tools-test.md)
- [Task 012 (impl): MCP tools](./task-012-mcp-tools-impl.md)
- [Task 013 (test): Reviewer agent](./task-013-reviewer-agent-test.md)
- [Task 013 (impl): Reviewer agent](./task-013-reviewer-agent-impl.md)
- [Task 014 (test): Frontend types and API client](./task-014-frontend-types-test.md)
- [Task 014 (impl): Frontend types and API client](./task-014-frontend-types-impl.md)
- [Task 015 (test): Frontend pages](./task-015-frontend-pages-test.md)
- [Task 015 (impl): Frontend pages](./task-015-frontend-pages-impl.md)
- [Task 016: Cleanup and service construction](./task-016-cleanup.md)

## BDD Coverage

All 55 BDD scenarios from the design are covered:

| Feature | Scenarios | Covered By |
|---------|-----------|------------|
| Feature 1: Content Spam Gate (13) | Stage 1 rules, AI gate, visibility, retry | Tasks 005, 007, 008, 013 |
| Feature 2: Agentbook Creation and Evolution (13) | CRUD, approval, hill-climbing, synthesis | Tasks 006, 007, 008, 010 |
| Feature 3: Outcome-based Confidence (12) | Basic outcomes, rate limit, self-report, recency, corroboration | Task 009 |
| Feature 4: Auto Research (12) | Candidates, cooldown, cycle recording, synthesis, locking | Task 010 |
| Feature 5: Token Economy (5) | Registration, outcome rewards, no self-reward | Task 009 |

## Dependency Chain

```
task-001 (setup)
    │
    ├─→ task-002-test → task-002-impl
    │       │
    │       ├─→ task-003-test → task-003-impl
    │       │
    │       ├─→ task-004-test → task-004-impl
    │       │       │
    │       │       └─→ task-006-test → task-006-impl
    │       │               │
    │       │               ├─→ task-007-test → task-007-impl
    │       │               │       │
    │       │               │       └─→ task-008-test → task-008-impl
    │       │               │               │
    │       │               │               ├─→ task-011-test → task-011-impl
    │       │               │               │       │
    │       │               │               │       └─→ task-014-test → task-014-impl
    │       │               │               │               │
    │       │               │               │               └─→ task-015-test → task-015-impl
    │       │               │               │                                       │
    │       │               │               └─→ task-012-test → task-012-impl       │
    │       │               │                                                        │
    │       │               ├─→ task-009-test → task-009-impl                       │
    │       │               │       │                                                │
    │       │               │       └─→ task-010-test → task-010-impl               │
    │       │               │                                                        │
    │       │               └─→ task-013-test → task-013-impl (also needs 007)      │
    │       │                                                                        │
    │       └─→ task-005-test → task-005-impl                                       │
    │                                                                                │
    └─→ task-016 (cleanup) ← depends on 011, 012, 013, 015 ◄──────────────────────┘
```

**Analysis:**
- No circular dependencies
- Parallel paths exist after task-002-impl: tasks 003, 004, 005 are independent of each other
- After task-006-impl, tasks 007, 009, 013 are independent
- After task-008-impl, tasks 011 and 012 are independent
- Task 016 aggregates all final implementations

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-03-19-unified-gate-research-plan/`. Execution options:

**1. Orchestrated Execution (Recommended)** — Load `superpowers:executing-plans` skill using the Skill tool.

**2. Direct Agent Team** — Load `superpowers:agent-team-driven-development` skill using the Skill tool.

**3. BDD-Focused Execution** — Load `superpowers:behavior-driven-development` skill for specific scenarios.
