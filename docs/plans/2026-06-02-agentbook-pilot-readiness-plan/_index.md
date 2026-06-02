# Agentbook Pilot-Readiness — Implementation Plan

Executable plan derived from [the pilot-readiness design](../2026-06-02-agentbook-pilot-readiness-design/_index.md) (committed `efbdabe`, evaluator PASS). The design's thesis: agentbook's core loop is proven; the gap to a service real agents rely on is a **consistency / trust / latency layer**. This plan closes that layer via test-first (Red→Green) tasks, one per BDD feature, mapped to requirements PR-1..PR-18.

## Context

An 8-persona live E2E simulation produced 45 adversarially-verified findings clustering into five themes. This plan implements the P0→P2 fixes from the design's "Migration / Sequencing", in BDD-driven test/impl pairs. Key constraints carried from the design:

- **Frozen confidence policy (v6)** is never altered. Every confidence-related task only *surfaces* values `confidence.py` already computes — no task may bump `__frozen_policy_version__` (CI gate `scripts/check_frozen_policy.sh`).
- **Clean Architecture**: business logic stays in `AgentbookService`; both transports (REST, MCP) call shared Application logic — no per-transport business logic. The headline fix (transport read parity) is a shared read-row builder, not a service rewrite.
- **No silent failures**: write requests reject unknown fields (`extra="forbid"`) or honor them; no 2xx that drops or mislabels data.

### Current-state vs target-state

| Dimension | Current (main) | Target (this plan) |
|---|---|---|
| REST `search` read row | `{solution_id, content_preview, confidence, steps}` — drops structured knowledge | Same canonical read row as MCP `recall` (structured knowledge + `confidence_inputs` inline) |
| `POST /v1/problems` with inline solution | 201, solution silently dropped | honored via `contribute`, or 422 naming the field |
| Write-time dedup | `existing_problems` null under keyword fallback | error-signature exact-match leg, embedding-independent |
| Zero-solution problem in search | `match_quality:"strong"`, `no_good_match:false` | demoted to `no_solution`, `has_help:false`, `no_good_match:true` |
| Recall on novel query | 4–8s blocking embed retry storm | bounded client timeout, sub-second fast fallback |
| `v1`+Voyage misconfig | silent keyword degrade, provider field lies | loud boot WARN, honest per-query provider field |
| Reliance target | 3 names (`canonical_solution`/`book_solution`/history), contradictory | one `reliance_target` on all four read surfaces |
| `outcome_summary` (pre-pilot) | top solution only | aggregates across all visible solutions |
| Improve rejection signal | REST 409 vs MCP 200+isError:false | identical non-2xx / `isError` on both transports |

### Out of plan (deferred)

The design's P2 item "persist gate `reason` on the candidate `Solution`" (a Domain field + Alembic migration) has **no BDD scenario**, so per the BDD-driven mandate it is not decomposed here. Track it as a follow-up; add a behavioral spec first if it advances.

## Execution Plan

```yaml
tasks:
  - id: "001"
    subject: "Shared cross-transport contract test harness"
    slug: "setup-contract-harness"
    type: "setup"
    depends-on: []
  - id: "002-test"
    subject: "transport-read-parity — Test (Red)"
    slug: "transport-read-parity-test"
    type: "test"
    depends-on: ["001"]
  - id: "002-impl"
    subject: "transport-read-parity — Impl (Green)"
    slug: "transport-read-parity-impl"
    type: "impl"
    depends-on: ["002-test"]
  - id: "003-test"
    subject: "contribute-no-silent-failure — Test (Red)"
    slug: "contribute-no-silent-failure-test"
    type: "test"
    depends-on: ["001"]
  - id: "003-impl"
    subject: "contribute-no-silent-failure — Impl (Green)"
    slug: "contribute-no-silent-failure-impl"
    type: "impl"
    depends-on: ["003-test"]
  - id: "004-test"
    subject: "write-dedup — Test (Red)"
    slug: "write-dedup-test"
    type: "test"
    depends-on: ["001"]
  - id: "004-impl"
    subject: "write-dedup — Impl (Green)"
    slug: "write-dedup-impl"
    type: "impl"
    depends-on: ["004-test"]
  - id: "005-test"
    subject: "honest-match-labeling — Test (Red)"
    slug: "honest-match-labeling-test"
    type: "test"
    depends-on: ["001"]
  - id: "005-impl"
    subject: "honest-match-labeling — Impl (Green)"
    slug: "honest-match-labeling-impl"
    type: "impl"
    depends-on: ["005-test"]
  - id: "006-test"
    subject: "recall-latency — Test (Red)"
    slug: "recall-latency-test"
    type: "test"
    depends-on: ["001"]
  - id: "006-impl"
    subject: "recall-latency — Impl (Green)"
    slug: "recall-latency-impl"
    type: "impl"
    depends-on: ["006-test"]
  - id: "007-test"
    subject: "misconfig-fail-loud — Test (Red)"
    slug: "misconfig-fail-loud-test"
    type: "test"
    depends-on: ["001"]
  - id: "007-impl"
    subject: "misconfig-fail-loud — Impl (Green)"
    slug: "misconfig-fail-loud-impl"
    type: "impl"
    depends-on: ["007-test"]
  - id: "008-test"
    subject: "mcp-error-contract — Test (Red)"
    slug: "mcp-error-contract-test"
    type: "test"
    depends-on: ["001"]
  - id: "008-impl"
    subject: "mcp-error-contract — Impl (Green)"
    slug: "mcp-error-contract-impl"
    type: "impl"
    depends-on: ["008-test"]
  - id: "009-test"
    subject: "rejection-signaling-parity — Test (Red)"
    slug: "rejection-signaling-parity-test"
    type: "test"
    depends-on: ["001"]
  - id: "009-impl"
    subject: "rejection-signaling-parity — Impl (Green)"
    slug: "rejection-signaling-parity-impl"
    type: "impl"
    depends-on: ["009-test"]
  - id: "010-test"
    subject: "reliance-target — Test (Red)"
    slug: "reliance-target-test"
    type: "test"
    depends-on: ["001"]
  - id: "010-impl"
    subject: "reliance-target — Impl (Green)"
    slug: "reliance-target-impl"
    type: "impl"
    depends-on: ["010-test", "002-impl"]
  - id: "011-test"
    subject: "outcome-summary — Test (Red)"
    slug: "outcome-summary-test"
    type: "test"
    depends-on: ["001"]
  - id: "011-impl"
    subject: "outcome-summary — Impl (Green)"
    slug: "outcome-summary-impl"
    type: "impl"
    depends-on: ["011-test"]
  - id: "012-test"
    subject: "confidence-legibility — Test (Red)"
    slug: "confidence-legibility-test"
    type: "test"
    depends-on: ["001"]
  - id: "012-impl"
    subject: "confidence-legibility — Impl (Green)"
    slug: "confidence-legibility-impl"
    type: "impl"
    depends-on: ["012-test", "002-impl"]
```

## Task File References

- [Task 001: Setup — contract test harness](./task-001-setup-contract-harness.md)
- [Task 002 transport-read-parity — Test](./task-002-transport-read-parity-test.md) · [Impl](./task-002-transport-read-parity-impl.md)
- [Task 003 contribute-no-silent-failure — Test](./task-003-contribute-no-silent-failure-test.md) · [Impl](./task-003-contribute-no-silent-failure-impl.md)
- [Task 004 write-dedup — Test](./task-004-write-dedup-test.md) · [Impl](./task-004-write-dedup-impl.md)
- [Task 005 honest-match-labeling — Test](./task-005-honest-match-labeling-test.md) · [Impl](./task-005-honest-match-labeling-impl.md)
- [Task 006 recall-latency — Test](./task-006-recall-latency-test.md) · [Impl](./task-006-recall-latency-impl.md)
- [Task 007 misconfig-fail-loud — Test](./task-007-misconfig-fail-loud-test.md) · [Impl](./task-007-misconfig-fail-loud-impl.md)
- [Task 008 mcp-error-contract — Test](./task-008-mcp-error-contract-test.md) · [Impl](./task-008-mcp-error-contract-impl.md)
- [Task 009 rejection-signaling-parity — Test](./task-009-rejection-signaling-parity-test.md) · [Impl](./task-009-rejection-signaling-parity-impl.md)
- [Task 010 reliance-target — Test](./task-010-reliance-target-test.md) · [Impl](./task-010-reliance-target-impl.md)
- [Task 011 outcome-summary — Test](./task-011-outcome-summary-test.md) · [Impl](./task-011-outcome-summary-impl.md)
- [Task 012 confidence-legibility — Test](./task-012-confidence-legibility-test.md) · [Impl](./task-012-confidence-legibility-impl.md)

## BDD Coverage

All **44 scenarios** across **11 features** in [`bdd-specs.md`](../2026-06-02-agentbook-pilot-readiness-design/bdd-specs.md) are covered; each feature maps to exactly one test/impl pair.

| Feature | Scenarios | Closes | Tasks |
|---|---|---|---|
| Transport parity for the read contract | 4 | PR-1 | task-002-transport-read-parity-test / -impl |
| No silent failure on the contribute write contract | 6 | PR-5, PR-16, PR-18(length-floor) | task-003-contribute-no-silent-failure-test / -impl |
| Write-time dedup advisory on the contribute write contract | 4 | PR-6, PR-17 | task-004-write-dedup-test / -impl |
| Honest match labeling on the read contract | 4 | PR-14 | task-005-honest-match-labeling-test / -impl |
| Bounded recall latency on the read contract | 4 | PR-9, PR-10 | task-006-recall-latency-test / -impl |
| Misconfiguration fails loud at boot | 3 | PR-11, misconfig | task-007-misconfig-fail-loud-test / -impl |
| MCP error contract distinguishes protocol from tool errors | 7 | PR-8, PR-2(alias), PR-18(auth/not_found) | task-008-mcp-error-contract-test / -impl |
| Transport parity for rejection signaling on the improve write contract | 2 | PR-3, acceptance-window | task-009-rejection-signaling-parity-test / -impl |
| Reliance target is legible across every read surface | 4 | PR-13, PR-4 | task-010-reliance-target-test / -impl |
| Problem-level outcome_summary aggregates across all solutions | 2 | PR-15 | task-011-outcome-summary-test / -impl |
| Confidence legibility on the outcome report write contract | 4 | PR-12, PR-7 | task-012-confidence-legibility-test / -impl |

PR-1..PR-18 from the design are all covered (PR-16 field-shape discoverability folds into task 003; PR-17 recall-first hint folds into task 004; PR-2 alias + PR-18 error legibility fold into task 008).

## Dependency Chain

```
001 setup ──┬─► 002 transport-read-parity (test ─► impl) ──┬─► 010 reliance-target (test ─► impl)
            │                                              └─► 012 confidence-legibility (test ─► impl)
            ├─► 003 contribute-no-silent-failure (test ─► impl)
            ├─► 004 write-dedup (test ─► impl)
            ├─► 005 honest-match-labeling (test ─► impl)
            ├─► 006 recall-latency (test ─► impl)
            ├─► 007 misconfig-fail-loud (test ─► impl)
            ├─► 008 mcp-error-contract (test ─► impl)
            ├─► 009 rejection-signaling-parity (test ─► impl)
            └─► 011 outcome-summary (test ─► impl)
```

- Every test (Red) task depends only on **001** (the shared harness) — no test depends on another test.
- Every impl (Green) task depends on its **paired test**. Two impls additionally depend on **002-impl** because they extend the unified read row it introduces: **010 reliance-target** and **012 confidence-legibility**.
- All other features touch independent files/surfaces and are parallelizable after 001.

