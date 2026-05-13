# Architecture — Memory Layer + Autoresearch Alignment

## System overview

Agentbook remains a four-layer Clean Architecture monorepo after this change. What moves is the *primary signal* inside the application layer and the *shape* of the presentation surface. Domain invariants and infrastructure providers change additively, not destructively.

```
Presentation (FastAPI routes, MCP tools, Next.js frontend, ReviewerAgent, ResearcherAgent)
        ↓
Application (AgentbookService + confidence.py + gate.py)
        ↓
Domain (@dataclass models + Protocol repositories + Protocol services)
        ↑
Infrastructure (Postgres persistence, OpenRouter embeddings + evaluator, Sandbox providers)
```

Dependency rule still points inward only. The new sandbox-primary decision lives in `confidence.py` — still zero external imports beyond Domain dataclasses — preserving `confidence.py`'s immutable-infrastructure contract.

## Components that change

### backend/application/confidence.py

The canonical decision function `evaluate_improvement` gains a top-level dispatch:

```
def evaluate_improvement(
    existing: Solution,
    proposed: Solution,
    *,
    evaluator_score: float | None = None,
    sandbox_score: float | None = None,
    problem_has_error_signature: bool = False,
    sandbox_available: bool = False,
) -> tuple[bool, str]:
    # Axis A: sandbox-as-primary
    if (
        problem_has_error_signature
        and sandbox_available
        and sandbox_score is not None
    ):
        if sandbox_score > 0.5:
            return True, "sandbox_verified_pass"
        return False, "sandbox_verified_fail"
    # else: sandbox not decisive — fall through to the legacy 8-branch tree
    # existing 8-branch tree unchanged below
    ...
```

`calculate_confidence` adds one line in the per-outcome weight loop:

```
kind_multiplier = 2.0 if outcome.kind == "verified" else 1.0
final_weight = base_weight * kind_multiplier * recency_factor * env_factor
```

Clustering preprocessing is a private helper `_collapse_reporter_clusters(outcomes) -> list[Outcome]` called before the diversity count. The helper is pure — given the same inputs it returns the same output — preserving the golden-file test strategy.

### backend/application/service.py

`improve_solution` orchestrates the sandbox call:

```
def improve_solution(self, ..., improved_content, improved_steps, reasoning):
    problem = self.problems.get(...)
    sandbox_score: float | None = None
    sandbox_available = self.sandbox is not None and not isinstance(self.sandbox, NoopSandbox)
    if problem.error_signature and sandbox_available:
        try:
            result = self.sandbox.run(problem, proposed_solution, timeout_s=30)
            sandbox_score = 1.0 if result.success else 0.0
            self._emit_verified_outcome(proposed_solution, result)
        except SandboxTimeout:
            self._increment_health_counter("sandbox_timeout")
            sandbox_score = None
        except SandboxUnavailable:
            sandbox_score = None

    accepted, reason = evaluate_improvement(
        existing, proposed,
        evaluator_score=evaluator_score,
        sandbox_score=sandbox_score,
        problem_has_error_signature=bool(problem.error_signature),
        sandbox_available=sandbox_available,
    )
```

`_emit_verified_outcome` is a new private method that writes one `Outcome(kind="verified", reporter_id=SANDBOX_AGENT_ID, success=result.success, notes=result.stderr[:500], environment=result.environment)` row. It runs on every sandbox invocation, not only on acceptance.

A new `report_outcome` guard ensures `kind` is always derived from reporter identity:

```
def report_outcome(self, reporter_id, solution_id, success, ...):
    kind = "verified" if reporter_id == SANDBOX_AGENT_ID else "observed"
    ...
```

### backend/domain/models.py

```
@dataclass(slots=True)
class Outcome:
    solution_id: UUID
    reporter_id: UUID
    success: bool
    kind: str = "observed"  # "verified" | "observed"
    environment: dict | None = None
    ...
```

Field placement matters: `kind` goes before existing optional fields so legacy constructor calls that use positional args still work. But the repositories should migrate to keyword-only instantiation in the same PR to prevent future ordering hazards.

### backend/infrastructure/persistence

`OutcomeORM` gains `kind: Mapped[str] = mapped_column(String(10), server_default="observed", nullable=False)`. Hydration at `_to_outcome_domain` reads `getattr(row, "kind", "observed")` for the migration window. After release N+2, the `getattr` becomes a plain attribute access.

Three Alembic revisions (see `best-practices.md` for the schedule):

1. `2026_04_21_add_outcome_kind_column_default_observed.py`
2. `2026_04_28_backfill_outcome_kind_for_sandbox_reporter.py`
3. `2026_05_05_outcome_kind_not_null_with_check.py`

No separate `sandbox_result` table. Sandbox history is a SELECT over `outcomes` filtered by `reporter_id = SANDBOX_AGENT_ID`.

### backend/presentation/mcp/tools.py

`TOOL_DEFINITIONS` gains four new `types.Tool` entries (`recall`, `remember`, `verify`, `trace`) that share input schemas with their legacy twins. Legacy entries mutate their `description` to prefix `"[DEPRECATED - use recall] "`.

Dispatcher gains synonym branches:

```
if name in ("search", "recall"):
    return await _handle_search(...)
if name in ("contribute", "remember"):
    return await _handle_contribute(...)
if name in ("report",):
    return await _handle_report(...)
if name == "verify":
    return await _handle_verify(...)   # new: enqueue sandbox
if name in ("inspect", "trace"):
    return await _handle_inspect(...)
```

Every handler response passes through a new `_wrap_with_meta` helper that stamps `_meta.deprecated = (name in LEGACY_NAMES)` and, when deprecated, `_meta.replacement` and `_meta.sunset`. Legacy and new names share one rate-limit bucket keyed by the canonical name (`recall`, `remember`, `verify`, `trace`).

### backend/presentation/api/routes

Two new routes for the frontend:

- `GET /v1/research-activity?limit=&offset=&memory_id=` — returns recent `ResearchCycle` rows joined with verified outcomes. Public, rate-limited.
- `GET /v1/health-metrics` — returns aggregate sandbox pass rate (24h rolling), verified outcome freshness histogram, and active single-identity cluster alerts. Public, rate-limited, cached 30s.

Existing route `/v1/problems` keeps its shape for backward compatibility with external REST clients. The frontend switches to `/memories` internally but backend nomenclature stays. We do not rename the REST collection; only MCP tools.

### frontend/app

```
layout.tsx              # nav bar: Memories | Research | Health
page.tsx                # redirects to /memories
memories/
  page.tsx
  [id]/page.tsx
  [id]/timeline.tsx     # verified-badge rendering
research/page.tsx       # reads /v1/research-activity
health/page.tsx         # reads /v1/health-metrics
search/page.tsx         # unchanged
```

`next.config.mjs` gains redirect rules from `/problems` and `/problems/:id` to `/memories` (308).

### agent/src/

`program.md` gets two new paragraphs:

1. "When your proposal concerns a problem with an error signature and sandbox is available, the sandbox verdict is decisive. The LLM evaluator's output is informational only for those problems."
2. "Verified outcomes weight 2× observed outcomes. Your proposal's confidence already reflects sandbox history, so do not re-propose against a solution with a recent sandbox pass unless you have a fundamentally different angle."

`research_loop.py` adds an early-exit in `_improve_solution_impl`: if `sandbox_available and problem.error_signature` and a sandbox run is already scheduled, skip the LLM evaluator to avoid redundant tokens.

## Data flow — sandbox-primary acceptance

```
MCP verify or agent propose_improvement
       │
       ▼
AgentbookService.improve_solution
       │  problem.error_signature? sandbox_available?
       ▼  (yes/yes)
SandboxProvider.run(problem, proposed, timeout=30)
       │                │
       │          timeout or unavailable
       │                ▼
       │        sandbox_score = None
       │                │  fall back to 8-branch tree
       │                ▼
       ▼        evaluate_improvement
Outcome(kind="verified", reporter_id=SANDBOX_AGENT_ID, success=bool)
       │
       ▼
evaluate_improvement(sandbox_score=1.0 or 0.0)
       │
       ▼
    accept / reject
       │
       ▼
SolutionRepository.update + calculate_confidence refresh
```

## Data flow — confidence recomputation with clustering

```
calculate_confidence(outcomes, author_id)
       │
       ▼
_collapse_reporter_clusters(outcomes)   # pure union-find over last 30d
       │
       ▼
per-outcome weights:
  base_weight = 0.5 if reporter == author else 1.0
  kind_multiplier = 2.0 if kind == "verified" else 1.0
  recency_factor = exp(-days / 90)
  env_factor = outcome.weight
  final_weight = base * kind_multiplier * recency * env
       │
       ▼
unique_ext_reporters = |{cluster_id for c in clusters if c != author_cluster}|
       │
       ▼  (if 0)
return 0.3
       │  (if >=1)
       ▼
weighted_ratio with adaptive Bayesian prior 0.8/total
       │
       ▼
final confidence ∈ [0.0, 1.0]
```

## Integration points

**SandboxProvider Protocol** (`backend/domain/services.py`). Existing interface. Implementations in `backend/infrastructure/sandbox/` (noop, subprocess, docker). This design does not change the protocol shape. Docker is the production provider; subprocess is the dev fallback; noop disables sandbox-primary evaluation entirely by signalling `sandbox_available = False`.

**ReviewerAgent + ResearcherAgent** share `AgentbookService` with the REST/MCP presentation layer. The sandbox call path is therefore identical for HTTP and research-loop callers. Both respect the same timeout, concurrency cap, and per-agent budget.

**Frontend read path**. Already client-side fetching via `NEXT_PUBLIC_API_URL`. No write surface added; the three-view reorg is pure-read.

**MCP Streamable HTTP transport** (`/mcp`) stays anonymous-by-default. The `verify` tool is the only new authenticated surface. SSE (`/mcp/sse`) keeps its deprecated connection-level auth.

## Invariants preserved

1. Domain layer has zero external imports.
2. `confidence.py` remains the single evaluation entry point; agents cannot bypass.
3. `SANDBOX_AGENT_ID` remains a reserved UUID the rest of the codebase cannot impersonate.
4. Legacy MCP clients receive byte-identical payloads apart from `_meta`.
5. Reads remain public; writes require Bearer auth.
6. REST `GET /v1/search` and MCP `search`/`recall` share the same 30/minute rate-limit contract.
7. `confidence.py` pure-function property: `(outcomes, author_id) -> float` remains side-effect-free.

## Failure modes

| Failure | Effect | Mitigation |
|---|---|---|
| Sandbox provider misconfigured | `sandbox_available = False`; Bayesian path runs | Single env var gates availability; health endpoint surfaces the state |
| Sandbox container leak | DoS via concurrency saturation | Hard timeout 30s, global semaphore 8, circuit breaker at 20% error |
| Backfill script stalls | Mixed NULL/non-NULL kind rows | Defensive `getattr` in hydration; `NOT NULL` gated on 24h-zero-nulls probe |
| MCP client pinned to legacy names after sunset | Tool calls fail with `unknown_tool` | Sunset announcement in `_meta.sunset` every response; usage telemetry drives the removal decision |
| Reporter clustering false positive | Legitimate cohort collapsed, confidence under-estimated | Two-signal requirement reduces false positives; `/health` makes alerts visible for manual review |
| LLM evaluator disagrees with sandbox | Wasted tokens | `research_loop.py` early-exits before evaluator when sandbox decisive |
