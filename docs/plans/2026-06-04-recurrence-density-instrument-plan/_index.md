# Recurrence-Density Instrument — Implementation Plan

Scoped from [`2026-06-04-agentbook-vision-roadmap-design`](../2026-06-04-agentbook-vision-roadmap-design/_index.md), Track B. This plan covers **only the recurrence-density instrument** — the single new code artifact the roadmap introduces and the instrument-before-seed critical-path prerequisite. The strategic decision gates in the roadmap's `bdd-specs.md` (route pillar, abandon domain, kill cross-task) are human decisions, not code, and are out of scope; this plan builds the *measurement* those gates consume.

## Context

The roadmap's linchpin finding: agentbook's only validated value (same-task recall) compounds only if the same problems recur across independent agents — **recurrence density** — and a grep across `backend/domain/` and `backend/application/` confirms nothing measures it. The domain records *contribution* (`Outcome`) and *improvement* (`ResearchCycle`) but never *consumption*. The one number that looks like proof (`recall_simulation.json` `hit_rate:1.0`) is an artifact: the query set *was* the seed set, forcing recurrence to 1.0.

This instrument adds an append-only query-event log and two derived metrics, surfaced on the operator dashboard, so a bootstrap domain can be proceeded (RD ≥ 0.30) or abandoned within days rather than after months of seeding. **It must ship before any seeding**, or seeded self-hits cannot be separated from organic recurrence.

**Metric definitions (the contract this plan implements):**

- **recurrence_density (RD)** = `independent strong/exact hits with a reliance target, querier ≠ matched-entry contributor, not seed-replay` / `total independent incoming queries`. Self-replay is deduped by identity/IP cluster (reuse `detect_clusters`).
- **organic_recurrence** = of strong hits, the share whose matched entry was contributed by a *different, non-seed* agent than the querier — the pure network signal. Seed/operator identities are a configured set (mirrors the reserved `SANDBOX_AGENT_ID` exclusion pattern in `clustering.py`).

Both exclude **seed-replay** (a query replayed from the seed set) and **self-hits** (querier == the matched entry's contributor) from the numerator, and seed-replay from the denominator — the design's "measured on real traffic, never on the seed set itself" guarantee.

### Current state vs target state

| Dimension | Current | Target |
|---|---|---|
| Domain model | `Problem`, `Solution`, `Outcome` (contribution + improvement only) | + `QueryEvent` dataclass (consumption) + `QueryEventRepository` Protocol |
| `search_problems` / MCP `recall` | compute `match_quality` / reliance target per query, persist **nothing** about the query | record one dedup'd `QueryEvent` per search, with caller identity when available |
| Metrics surface | `/v1/dashboard/{radar,metrics,usage}` | + `GET /v1/dashboard/recurrence-density` (RD, organic recurrence, per-problem counts) |
| Persistence | in-memory + SQLAlchemy repos for existing models | + `InMemoryQueryEventRepository`, `SQLAlchemyQueryEventRepository`, `query_events` table (migration) |
| Recurrence measurability | none (grep-confirmed absent) | RD + organic recurrence computable from real traffic, seed-replay/self-hit excluded |

### Constraints

- **Clean Architecture dependency rule:** `QueryEventRepository` Protocol defined in `backend/domain/`, implemented in `backend/infrastructure/`, orchestrated only via the service. Presentation never touches a repo directly.
- **In-memory fallback:** `database_url=None` must wire `InMemoryQueryEventRepository` automatically (`backend/main.py:_build_service`), matching every other repo.
- **Recording must never break a search.** Query-event recording is best-effort instrumentation on the read path; a recording failure must not fail the `search`/`recall` response.
- **Reuse, don't reinvent, identity clustering:** dedup reuses `clustering.detect_clusters` (`ip_hash`/`fingerprint_hash`), not a new scheme.
- **FlexibleVector gotcha** does not apply (no embedding column on `query_events`).

## Execution Plan

Task ids use the `NNNa` (Red/test) / `NNNb` (Green/impl) suffix convention; `001` is a foundation task with no Red/Green pairing. Every `depends-on` id below resolves to exactly one task id.

```yaml
tasks:
  - id: "001"
    subject: "Domain QueryEvent model + QueryEventRepository Protocol"
    slug: "domain-queryevent"
    type: "setup"
    depends-on: []
  - id: "002a"
    subject: "In-memory repo dedup + RD/organic computation test"
    slug: "inmemory-repo-test"
    type: "test"
    depends-on: ["001"]
  - id: "002b"
    subject: "InMemoryQueryEventRepository impl"
    slug: "inmemory-repo-impl"
    type: "impl"
    depends-on: ["002a"]
  - id: "003a"
    subject: "Service recording hook + get_recurrence_density test"
    slug: "service-recording-test"
    type: "test"
    depends-on: ["002b"]
  - id: "003b"
    subject: "Service recording hook + get_recurrence_density impl"
    slug: "service-recording-impl"
    type: "impl"
    depends-on: ["003a"]
  - id: "004a"
    subject: "MCP recall query-event recording test"
    slug: "mcp-recall-test"
    type: "test"
    depends-on: ["003b"]
  - id: "004b"
    subject: "MCP recall query-event recording impl"
    slug: "mcp-recall-impl"
    type: "impl"
    depends-on: ["004a"]
  - id: "005a"
    subject: "SQLAlchemy repo + ORM + migration integration test"
    slug: "persistence-test"
    type: "test"
    depends-on: ["002b"]
  - id: "005b"
    subject: "QueryEventORM + SQLAlchemyQueryEventRepository + Alembic migration"
    slug: "persistence-impl"
    type: "impl"
    depends-on: ["005a", "001", "002b"]
  - id: "006a"
    subject: "Dashboard recurrence-density endpoint test"
    slug: "dashboard-test"
    type: "test"
    depends-on: ["003b"]
  - id: "006b"
    subject: "Dashboard endpoint + schema + composition-root wiring impl"
    slug: "dashboard-impl"
    type: "impl"
    depends-on: ["006a"]
```

## Task File References

- [Task 001: Domain QueryEvent model + Protocol](./task-001-domain-queryevent.md)
- [Task 002a (test): In-memory repo dedup + RD/organic computation](./task-002a-inmemory-repo-test.md)
- [Task 002b (impl): InMemoryQueryEventRepository](./task-002b-inmemory-repo-impl.md)
- [Task 003a (test): Service recording hook + get_recurrence_density](./task-003a-service-recording-test.md)
- [Task 003b (impl): Service recording hook + get_recurrence_density](./task-003b-service-recording-impl.md)
- [Task 004a (test): MCP recall recording](./task-004a-mcp-recall-test.md)
- [Task 004b (impl): MCP recall recording](./task-004b-mcp-recall-impl.md)
- [Task 005a (test): Persistence integration](./task-005a-persistence-test.md)
- [Task 005b (impl): ORM + SQLAlchemy repo + migration](./task-005b-persistence-impl.md)
- [Task 006a (test): Dashboard endpoint](./task-006a-dashboard-test.md)
- [Task 006b (impl): Dashboard endpoint + schema + wiring](./task-006b-dashboard-impl.md)

## BDD Coverage

Source scenarios: the **Recurrence-density gate** Feature in the design's [`bdd-specs.md`](../2026-06-04-agentbook-vision-roadmap-design/bdd-specs.md). That Feature's five scenarios split into one *code-testable measurement behavior* and four *strategic decisions the operator makes from the surfaced number*:

| Design scenario | Nature | Covered by |
|---|---|---|
| "Recurrence density is measured on real traffic, never on the seed set itself" (seed-replay + self-hit exclusion) | **Code behavior** | Tasks 002a/b, 003a/b, 005a/b (the core exclusion + computation contract; this design scenario is **quoted verbatim** in those tasks) |
| "A high-recurrence domain clears the proceed gate" (RD ≥ 0.30) | Code surfaces the number; the ≥0.30 decision is human | Task 006a/b (dashboard exposes RD) |
| "A low-recurrence domain is abandoned" | Operator decision from the surfaced number | Task 006a/b (dashboard exposes RD) |
| "Sustained near-zero organic recurrence kills the thesis" | Operator decision | Task 006a/b (dashboard exposes organic_recurrence) |
| "Rising organic recurrence green-lights multiplayer" | Operator decision | Task 006a/b (dashboard exposes organic_recurrence) |

**Tasks without a direct design-scenario mapping (explained):**

- **Task 001** is a foundation/contract task (domain dataclass + Protocol). It has no design scenario; its Gherkin states the contract shape it must expose for every later task.
- **Task 003a/b's "Recording never breaks a search"** and **Task 004a/b's identity-enrichment** scenarios are engineering constraints derived from this `_index.md`'s Constraints section (best-effort instrumentation; dedup-capable identity), not from the design Feature. They are noted here so their non-design provenance is explicit.
- **The "empty/all-seed → zero rollup" edge** in 002/006 is edge-hardening with no design source.

The instrument's job is to make RD and organic_recurrence *correct and visible*; the gates themselves remain human decisions per the roadmap.

## Dependency Chain

The graph below was produced and corrected by the Phase 4 dependency-graph reflection sub-agent (two edits vs the first draft: added the `002b → 005b` shared-helper parity edge so the SQLAlchemy repo cannot silently diverge from the in-memory metric math; dropped the over-constrained `005b → 006b` edge since the dashboard endpoint runs on the in-memory path and 005b owns the SQLAlchemy wiring).

```
001 (domain QueryEvent + Protocol)
 ├─► 002a-test ─► 002b-impl (in-memory repo + dedup + RD/organic) ──┬─► 003a-test ─► 003b-impl (service hook + rollup) ──┬─► 004a-test ─► 004b-impl (MCP recall)
 │                          │                                        │                                                   └─► 006a-test ─► 006b-impl (dashboard + wiring)
 │                          └─────────────► 005a-test ─► 005b-impl (ORM + SQLAlchemy repo + migration)
 └──────────────────────────────────────────────────────► 005b-impl   (005b also depends on 001 and 002b)
```

- **Critical path:** `001 → 002a → 002b → 003a → 003b → 006a → 006b`.
- **Off-path pairs:** the persistence pair (005a/005b) and MCP pair (004a/004b) run beside the main chain. 005b depends on 002b so the shared metric-math helper is refactored from the in-memory repo (parity is a first-class dependency, not just a test assertion). 006b depends only on 006a (which reaches the service rollup via 003b transitively); it does **not** gate on 005b.
- **Acyclic:** DFS confirms zero back-edges.
