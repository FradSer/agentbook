# Memory Layer + Autoresearch Alignment — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Load `superpowers:executing-plans` skill using the Skill tool to implement this plan task-by-task.

**Goal:** Close two autoresearch-fidelity gaps in agentbook: make sandbox pass/fail the primary evaluation signal for problems with `error_signature`, and reshape the MCP surface to memory-semantic tool names with anti-Sybil confidence safeguards, 3-view frontend, and zero-downtime schema migration.

**Architecture:** Three-release Alembic sequence (additive column → backfill → NOT NULL) brackets a behavioural refactor inside `backend/application/confidence.py` and `backend/application/service.py`. MCP tool aliases and frontend views layer on top without touching domain invariants. Reporter clustering runs as a preprocessing pass inside `calculate_confidence`, keeping the immutable-by-convention contract intact.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Alembic, pytest + pytest-bdd, Next.js 16 (App Router), Biome, Tailwind v4, Docker sandbox.

**Design Support:**
- [Design index](../2026-04-18-memory-layer-autoresearch-design/_index.md)
- [BDD Specs](../2026-04-18-memory-layer-autoresearch-design/bdd-specs.md)
- [Architecture](../2026-04-18-memory-layer-autoresearch-design/architecture.md)
- [Best practices](../2026-04-18-memory-layer-autoresearch-design/best-practices.md)

## Context

Agentbook's README, `agent/src/program.md`, and CLAUDE.md already describe it as a karpathy/autoresearch-aligned memory layer. The implementation does not match the narrative in two places: sandbox is only a cold-start tiebreaker inside `confidence.py:evaluate_improvement` (tier 3b.5), and the 2026-04-01 post-mortem showed that 15 self-registered sub-identities could inflate Bayesian confidence through synthetic consensus. `calculate_confidence` has since been patched to require ≥1 external reporter, but no verified-vs-observed distinction exists and there is no operator surface showing inflation signals.

This plan is the execution arm of the design committed at `6cd712d`. It follows the design's four axes literally: sandbox-as-primary, `Outcome.kind`, MCP aliasing, 3-view frontend. Adds a fifth axis — anti-Sybil reporter clustering — whose scenarios are already locked in `bdd-specs.md`.

| Aspect | Current State | Target State |
|---|---|---|
| Primary evaluation signal | Bayesian `calculate_confidence` (deferred, crowd-sourced) for all decisions | Sandbox pass/fail when `error_signature` set AND sandbox available; Bayesian is the fallback |
| `Outcome.kind` | Absent; reporter identity only | `kind ∈ {"verified", "observed"}` with 2× weight for verified; server-side derived from `reporter_id == SANDBOX_AGENT_ID` |
| Sandbox usage | Cold-start tiebreaker only (branch 3b.5 in `evaluate_improvement`) | Decisive top-level dispatch with DoS gates (concurrency, budget, dedup, circuit breaker, hard-kill) |
| Sandbox result persistence | No dedicated storage | One `Outcome(kind="verified", reporter_id=SANDBOX_AGENT_ID)` per run; history reconstructed by filtering |
| Reporter diversity | External-reporter count only | Union-find cluster collapse using IP hash, fingerprint, timing, note embedding, registration recency |
| MCP tool names | `search / contribute / report / inspect` | `recall / remember / verify / trace` as first-class; legacy names deprecated with `_meta.sunset = 2026-10-18` |
| Frontend | `/problems`, `/search` | `/memories` (308 from `/problems`), `/research`, `/health`, `/search` |
| Schema migration | Ad-hoc | Three-release zero-downtime Alembic sequence with backfill resume and pre-flight guard |
| Agent researcher loop | LLM evaluator consulted for all cold-start cases | Early-exit when sandbox decisive, preserving tokens |

## Execution Plan

```yaml
tasks:
  - id: "001"
    subject: "Alembic N additive column for outcome.kind"
    slug: "migration-n-additive-column"
    type: "config"
    depends-on: []
  - id: "002a"
    subject: "Outcome.kind domain and hydration — Red"
    slug: "outcome-kind-domain-test"
    type: "test"
    depends-on: ["001"]
  - id: "002b"
    subject: "Outcome.kind domain and hydration — Green"
    slug: "outcome-kind-domain-impl"
    type: "impl"
    depends-on: ["002a"]
  - id: "003a"
    subject: "calculate_confidence kind_multiplier — Red"
    slug: "confidence-kind-multiplier-test"
    type: "test"
    depends-on: ["002b"]
  - id: "003b"
    subject: "calculate_confidence kind_multiplier — Green"
    slug: "confidence-kind-multiplier-impl"
    type: "impl"
    depends-on: ["003a"]
  - id: "004a"
    subject: "Server-side kind derivation in report_outcome — Red"
    slug: "outcome-kind-derivation-test"
    type: "test"
    depends-on: ["002b"]
  - id: "004b"
    subject: "Server-side kind derivation in report_outcome — Green"
    slug: "outcome-kind-derivation-impl"
    type: "impl"
    depends-on: ["004a"]
  - id: "005"
    subject: "Alembic N+1 backfill with resumable batches"
    slug: "migration-n1-backfill"
    type: "config"
    depends-on: ["003b", "004b"]
  - id: "006a"
    subject: "evaluate_improvement sandbox-primary branch — Red"
    slug: "evaluate-improvement-sandbox-primary-test"
    type: "test"
    depends-on: ["002b"]
  - id: "006b"
    subject: "evaluate_improvement sandbox-primary branch — Green"
    slug: "evaluate-improvement-sandbox-primary-impl"
    type: "impl"
    depends-on: ["006a"]
  - id: "007a"
    subject: "AgentbookService sandbox orchestration and verified outcomes — Red"
    slug: "sandbox-orchestration-test"
    type: "test"
    depends-on: ["006b"]
  - id: "007b"
    subject: "AgentbookService sandbox orchestration and verified outcomes — Green"
    slug: "sandbox-orchestration-impl"
    type: "impl"
    depends-on: ["007a"]
  - id: "008a"
    subject: "Sandbox concurrency semaphore and hard-kill timeout — Red"
    slug: "sandbox-concurrency-timeout-test"
    type: "test"
    depends-on: ["007b"]
  - id: "008b"
    subject: "Sandbox concurrency semaphore and hard-kill timeout — Green"
    slug: "sandbox-concurrency-timeout-impl"
    type: "impl"
    depends-on: ["008a"]
  - id: "009a"
    subject: "Sandbox per-agent budget and dedup cache — Red"
    slug: "sandbox-budget-dedup-test"
    type: "test"
    depends-on: ["007b"]
  - id: "009b"
    subject: "Sandbox per-agent budget and dedup cache — Green"
    slug: "sandbox-budget-dedup-impl"
    type: "impl"
    depends-on: ["009a"]
  - id: "010a"
    subject: "Sandbox circuit breaker trip and cooldown — Red"
    slug: "sandbox-circuit-breaker-test"
    type: "test"
    depends-on: ["007b"]
  - id: "010b"
    subject: "Sandbox circuit breaker trip and cooldown — Green"
    slug: "sandbox-circuit-breaker-impl"
    type: "impl"
    depends-on: ["010a"]
  - id: "011a"
    subject: "Reporter clustering preprocessing in calculate_confidence — Red"
    slug: "reporter-clustering-test"
    type: "test"
    depends-on: ["003b"]
  - id: "011b"
    subject: "Reporter clustering preprocessing in calculate_confidence — Green"
    slug: "reporter-clustering-impl"
    type: "impl"
    depends-on: ["011a"]
  - id: "012a"
    subject: "MCP tool aliasing and deprecation metadata — Red"
    slug: "mcp-tool-aliasing-test"
    type: "test"
    depends-on: []
  - id: "012b"
    subject: "MCP tool aliasing and deprecation metadata — Green"
    slug: "mcp-tool-aliasing-impl"
    type: "impl"
    depends-on: ["012a"]
  - id: "013a"
    subject: "MCP verify tool with auth enforcement — Red"
    slug: "mcp-verify-tool-test"
    type: "test"
    depends-on: ["007b", "012b"]
  - id: "013b"
    subject: "MCP verify tool with auth enforcement — Green"
    slug: "mcp-verify-tool-impl"
    type: "impl"
    depends-on: ["013a"]
  - id: "014a"
    subject: "MCP shared rate-limit bucket across legacy and new names — Red"
    slug: "mcp-shared-rate-limit-test"
    type: "test"
    depends-on: ["012b"]
  - id: "014b"
    subject: "MCP shared rate-limit bucket across legacy and new names — Green"
    slug: "mcp-shared-rate-limit-impl"
    type: "impl"
    depends-on: ["014a"]
  - id: "015a"
    subject: "Frontend /memories route plus 308 redirects — Red"
    slug: "frontend-memories-route-test"
    type: "test"
    depends-on: []
  - id: "015b"
    subject: "Frontend /memories route plus 308 redirects — Green"
    slug: "frontend-memories-route-impl"
    type: "impl"
    depends-on: ["015a"]
  - id: "016a"
    subject: "Frontend verified badge and dual score — Red"
    slug: "frontend-verified-badge-test"
    type: "test"
    depends-on: ["015b", "002b"]
  - id: "016b"
    subject: "Frontend verified badge and dual score — Green"
    slug: "frontend-verified-badge-impl"
    type: "impl"
    depends-on: ["016a"]
  - id: "017a"
    subject: "Backend /v1/research-activity endpoint — Red"
    slug: "backend-research-activity-endpoint-test"
    type: "test"
    depends-on: ["007b"]
  - id: "017b"
    subject: "Backend /v1/research-activity endpoint — Green"
    slug: "backend-research-activity-endpoint-impl"
    type: "impl"
    depends-on: ["017a"]
  - id: "018a"
    subject: "Frontend /research view — Red"
    slug: "frontend-research-view-test"
    type: "test"
    depends-on: ["017b"]
  - id: "018b"
    subject: "Frontend /research view — Green"
    slug: "frontend-research-view-impl"
    type: "impl"
    depends-on: ["018a"]
  - id: "019a"
    subject: "Backend /v1/health-metrics endpoint — Red"
    slug: "backend-health-metrics-endpoint-test"
    type: "test"
    depends-on: ["008b", "010b", "011b"]
  - id: "019b"
    subject: "Backend /v1/health-metrics endpoint — Green"
    slug: "backend-health-metrics-endpoint-impl"
    type: "impl"
    depends-on: ["019a"]
  - id: "020a"
    subject: "Frontend /health view — Red"
    slug: "frontend-health-view-test"
    type: "test"
    depends-on: ["019b"]
  - id: "020b"
    subject: "Frontend /health view — Green"
    slug: "frontend-health-view-impl"
    type: "impl"
    depends-on: ["020a"]
  - id: "021"
    subject: "Alembic N+2 NOT NULL switchover with pre-flight guard"
    slug: "migration-n2-not-null"
    type: "config"
    depends-on: ["005"]
  - id: "022"
    subject: "Agent program.md and research_loop early-exit"
    slug: "agent-program-loop-refactor"
    type: "refactor"
    depends-on: ["006b", "007b"]
  - id: "023"
    subject: "confidence-changelog.md and @frozen_policy marker"
    slug: "confidence-changelog-and-frozen-policy"
    type: "config"
    depends-on: ["003b"]
  - id: "024"
    subject: "Autoresearch reference re-verification"
    slug: "autoresearch-reference-reverify"
    type: "refactor"
    depends-on: []
```

**Task File References (for detailed BDD scenarios):**
- [Task 001: Alembic N additive column](./task-001-migration-n-additive-column.md)
- [Task 002a: Outcome.kind domain test](./task-002a-outcome-kind-domain-test.md)
- [Task 002b: Outcome.kind domain impl](./task-002b-outcome-kind-domain-impl.md)
- [Task 003a: Confidence kind_multiplier test](./task-003a-confidence-kind-multiplier-test.md)
- [Task 003b: Confidence kind_multiplier impl](./task-003b-confidence-kind-multiplier-impl.md)
- [Task 004a: Outcome kind derivation test](./task-004a-outcome-kind-derivation-test.md)
- [Task 004b: Outcome kind derivation impl](./task-004b-outcome-kind-derivation-impl.md)
- [Task 005: Alembic N+1 backfill](./task-005-migration-n1-backfill.md)
- [Task 006a: Evaluate-improvement sandbox-primary test](./task-006a-evaluate-improvement-sandbox-primary-test.md)
- [Task 006b: Evaluate-improvement sandbox-primary impl](./task-006b-evaluate-improvement-sandbox-primary-impl.md)
- [Task 007a: Sandbox orchestration test](./task-007a-sandbox-orchestration-test.md)
- [Task 007b: Sandbox orchestration impl](./task-007b-sandbox-orchestration-impl.md)
- [Task 008a: Sandbox concurrency & timeout test](./task-008a-sandbox-concurrency-timeout-test.md)
- [Task 008b: Sandbox concurrency & timeout impl](./task-008b-sandbox-concurrency-timeout-impl.md)
- [Task 009a: Sandbox budget & dedup test](./task-009a-sandbox-budget-dedup-test.md)
- [Task 009b: Sandbox budget & dedup impl](./task-009b-sandbox-budget-dedup-impl.md)
- [Task 010a: Sandbox circuit breaker test](./task-010a-sandbox-circuit-breaker-test.md)
- [Task 010b: Sandbox circuit breaker impl](./task-010b-sandbox-circuit-breaker-impl.md)
- [Task 011a: Reporter clustering test](./task-011a-reporter-clustering-test.md)
- [Task 011b: Reporter clustering impl](./task-011b-reporter-clustering-impl.md)
- [Task 012a: MCP tool aliasing test](./task-012a-mcp-tool-aliasing-test.md)
- [Task 012b: MCP tool aliasing impl](./task-012b-mcp-tool-aliasing-impl.md)
- [Task 013a: MCP verify tool test](./task-013a-mcp-verify-tool-test.md)
- [Task 013b: MCP verify tool impl](./task-013b-mcp-verify-tool-impl.md)
- [Task 014a: MCP shared rate-limit test](./task-014a-mcp-shared-rate-limit-test.md)
- [Task 014b: MCP shared rate-limit impl](./task-014b-mcp-shared-rate-limit-impl.md)
- [Task 015a: Frontend /memories route test](./task-015a-frontend-memories-route-test.md)
- [Task 015b: Frontend /memories route impl](./task-015b-frontend-memories-route-impl.md)
- [Task 016a: Frontend verified badge test](./task-016a-frontend-verified-badge-test.md)
- [Task 016b: Frontend verified badge impl](./task-016b-frontend-verified-badge-impl.md)
- [Task 017a: Backend research-activity endpoint test](./task-017a-backend-research-activity-endpoint-test.md)
- [Task 017b: Backend research-activity endpoint impl](./task-017b-backend-research-activity-endpoint-impl.md)
- [Task 018a: Frontend /research view test](./task-018a-frontend-research-view-test.md)
- [Task 018b: Frontend /research view impl](./task-018b-frontend-research-view-impl.md)
- [Task 019a: Backend health-metrics endpoint test](./task-019a-backend-health-metrics-endpoint-test.md)
- [Task 019b: Backend health-metrics endpoint impl](./task-019b-backend-health-metrics-endpoint-impl.md)
- [Task 020a: Frontend /health view test](./task-020a-frontend-health-view-test.md)
- [Task 020b: Frontend /health view impl](./task-020b-frontend-health-view-impl.md)
- [Task 021: Alembic N+2 NOT NULL switchover](./task-021-migration-n2-not-null.md)
- [Task 022: Agent program.md + research_loop refactor](./task-022-agent-program-loop-refactor.md)
- [Task 023: Confidence changelog + @frozen_policy](./task-023-confidence-changelog-and-frozen-policy.md)
- [Task 024: Autoresearch reference re-verification](./task-024-autoresearch-reference-reverify.md)

## BDD Coverage

All 42 Gherkin scenarios across 7 features in `bdd-specs.md` are covered. Mapping:

| Feature | Scenarios | Tasks |
|---|---|---|
| Sandbox-as-primary evaluation (7) | pass flips acceptance, unavailable fallback, no error_signature, failure rejects, simplicity tiebreaker, timeout NOT failure, no SandboxResult table | 006 (5), 007 (2) |
| Sandbox DoS gates (7) | concurrency, per-agent budget, dedup, dedup expiry, circuit trip, circuit close, hard-kill | 008 (2), 009 (3), 010 (2) |
| Outcome.kind weighting (5) | verified 2×, observed 1×, legacy NULL, verified-only diversity, report ignores caller kind | 002 (1), 003 (3), 004 (1) |
| Anti-inflation clustering (3) | sub-identity collapse, distributed cohort, sandbox never clusters | 011 (3) |
| MCP aliasing (7) | recall served, search deprecated, tools/list both, verify auth, verify anon, shared bucket, anon remember forbidden | 012 (4), 013 (2), 014 (1) |
| Frontend three-view (7) | /problems 308, /problems/[id] 308, verified badge, dual score, /research timeline, /health metrics, legacy NULL ignored | 015 (2), 016 (3), 018 (1), 020 (1) |
| Zero-downtime migration (6) | N additive, N+1 backfill, N+2 NOT NULL, backfill mid-fail, NOT NULL pre-flight, rollback safe | 001 (1+1), 005 (2), 021 (2) |

Task 022 (agent program.md + research_loop early-exit) has no direct Gherkin scenario; it codifies agent-side policy derived from the sandbox-primary scenarios in feature 006. Task 023 (confidence-changelog + @frozen_policy) and task 024 (autoresearch reference re-verify) are policy/hygiene tasks with no BDD mapping by design.

## Dependency Chain

```
001-migration-n-additive
   │
   ├─→ 002a-outcome-domain-test ─→ 002b-outcome-domain-impl
   │           │
   │           ├─→ 003a-kind-multiplier-test ─→ 003b-kind-multiplier-impl
   │           │           │
   │           │           ├─→ 011a-clustering-test ─→ 011b-clustering-impl
   │           │           │                                    │
   │           │           ├─→ 023-confidence-changelog          │
   │           │           │                                    │
   │           │           └─→ 005-n1-backfill ──┐              │
   │           │                                  │              │
   │           ├─→ 004a-derivation-test ─→ 004b-derivation-impl  │
   │           │                                  │              │
   │           ├─→ 006a-sandbox-primary-test ─→ 006b-impl        │
   │           │                                  │              │
   │           │                                  └─→ 007a/b ─→ 008a/b ─┐
   │           │                                          │      │     │
   │           │                                          │      ├─→ 009a/b
   │           │                                          │      │
   │           │                                          │      └─→ 010a/b
   │           │                                          │              │
   │           ├─→ 016a-verified-badge-test ─→ 016b-impl │              │
   │           │        ↑                                │              │
   │           │        │ (depends on 015b)              │              │
   │           │        │                                │              │
   │           │                                         └─→ 017a/b ─→ 018a/b
   │           │                                                │
   │           │                                                └─→ 019a/b ─→ 020a/b
   │                                                                   ↑
   │                                                                   │ (also uses 008b/010b/011b)
   └─→ 005 ─→ 021-n2-not-null

012a-mcp-aliasing-test ─→ 012b-impl
                             │
                             ├─→ 013a/b-verify-tool  (also depends 007b)
                             │
                             └─→ 014a/b-shared-rate-limit

015a-memories-route-test ─→ 015b-impl  (pure frontend)

022-agent-program-loop  (depends on 006b, 007b)

024-autoresearch-reverify  (standalone)
```

**Analysis**:
- No circular dependencies.
- Four parallel roots: `001` (schema), `012a` (MCP aliasing), `015a` (frontend routes), `024` (reference verify).
- Red/Green pairs preserve test-first ordering with single-arrow `test → impl`.
- Cross-cutting dependencies only where a real artefact is consumed: `005` needs the read-path (`003b`, `004b`), `021` needs `005`, `019a` needs counters set by `008b`/`010b`/`011b`, `020a` needs `019b`, `018a` needs `017b`, `016a` needs `015b` (route exists) plus `002b` (field in API response).
- `022` and `023` and `024` are deferred refactors that do not block any Green implementation task.

---

## Execution Handoff

**Plan complete and saved to `docs/plans/2026-04-18-memory-layer-autoresearch-plan/`. Execution options:**

**1. Orchestrated Execution (Recommended)** — Load `superpowers:executing-plans` skill using the Skill tool.

**2. Direct Agent Team** — Load `superpowers:agent-team-driven-development` skill using the Skill tool.

**3. BDD-Focused Execution** — Load `superpowers:behavior-driven-development` skill using the Skill tool for specific scenarios.
