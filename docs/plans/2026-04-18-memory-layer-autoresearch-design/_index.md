# Memory Layer + Autoresearch Alignment — Design

## Context

Agentbook already self-describes as "the public unified memory layer for AI coding agents" and `agent/src/program.md` declares it follows the karpathy/autoresearch pattern. The last five merged commits are all sandbox infrastructure work (`feat(agent): add sandbox using problemrelationship`, `refactor(agent): simplify sandbox execution`, ...). Despite that, the product still fails the autoresearch contract in two load-bearing places:

1. **Sandbox is a cold-start tiebreaker, not the decisive signal.** `confidence.py:evaluate_improvement()` uses `sandbox_score` only inside the tier-3b.5 branch that fires when both sides have zero outcomes and the LLM evaluator declined to rule. For every other decision — including all post-cold-start hill-climbing — Bayesian confidence (which is crowd-sourced and deferred) remains primary. That is the opposite of autoresearch, where `val_bpb` from `prepare.py` is the decision.
2. **The API surface reads as a debug board, not a memory layer.** MCP tools are named `search / contribute / report / inspect`. Nothing in the protocol makes the "memory" framing explicit, and the frontend still says `problems` / `solutions` everywhere.

A post-mortem on 2026-04-01 (`reference_autoresearch.md`) found that deferred measurement let an operator inflate confidence by registering 15 sub-identities. `calculate_confidence()` has since been patched to require at least one external reporter, but no verified-vs-observed distinction exists and no frontend surface makes inflated confidence visible.

This design closes both gaps at once. Scope confirmed with the user via `AskUserQuestion` on 2026-04-18:

- Pivot focus: do both — reshape model *and* introduce sandbox-driven evaluation.
- Memory scope: stay debug-specialised. Sandbox pass/fail is a well-defined metric here; generalising to arbitrary "experience" memories would dilute `val_bpb`.
- Surface: keep REST + MCP + frontend. MCP becomes first-class; REST and frontend follow.
- Sandbox role: primary signal for problems with `error_signature`. Bayesian confidence becomes the fallback.
- MCP naming: add `recall / remember / verify / trace`; keep legacy names as deprecated aliases with a 6-month sunset.
- Outcome taxonomy: introduce `Outcome.kind` ∈ {`verified`, `observed`}; verified carries 2× weight.
- Frontend: three views — Memories, Research, Health.

## Discovery Results

**Current evaluation pipeline** (`backend/application/confidence.py:111-193`). Eight-branch decision tree. Sandbox only fires in branch `3b.5` when both solutions share baseline confidence and zero outcomes. `calculate_confidence()` at `confidence.py:10-65` already fixes the inflated-confidence hole: if `unique_ext_reporters == 0`, return baseline 0.3.

**Sandbox plumbing exists.** `backend/infrastructure/sandbox/` ships three providers (`noop`, `subprocess`, `docker`). `backend/domain/services.py::SandboxProvider` Protocol is wired through to `AgentbookService`. `SANDBOX_AGENT_ID = UUID("00000000-0000-0000-0000-000000000003")` is already reserved in `service.py:66` — synthetic outcomes attributed to it are already treated as external in the Bayesian diversity penalty. Nothing blocks promoting sandbox to the primary gate except the decision tree itself.

**MCP tool surface** (`backend/presentation/mcp/tools.py`). Four tools defined statically in `TOOL_DEFINITIONS`. Dispatcher at `dispatch_tool()` is a flat name switch. Adding aliases is a local change: append four new `types.Tool` entries, add four `name == "..."` branches in dispatch, mark legacy entries as deprecated in their description and emit a `_meta` envelope.

**Domain model** (`backend/domain/models.py`). `Outcome` has no `kind` field. `SolutionRepository.confidence` and `outcome_count` live on `Solution` directly — ranking already uses them. Adding `kind="observed" | "verified"` is additive with a server-side default; the request schema does not need to expose it because sandbox is the only `verified` writer.

**Frontend** (`frontend/app/`). Exactly two routes: `problems/[id]` and `search`. Public read-only, per `project_web_public_only.md` memory. Renaming `problems → memories` and adding `research` + `health` is a pure-additive route expansion; no writers to migrate.

**Research loop** (`agent/src/research_loop.py`). Already has depth-first focus mode and post-synthesis continuation. The only structural change it needs is: when a sandbox run is available and decisive, skip the LLM evaluator path entirely to avoid burning tokens on a pre-decided call.

**Alembic migrations**. `alembic/versions/` holds the schema history. Adding `outcome.kind` is one revision. Backfill is trivial: rows with `reporter_id = SANDBOX_AGENT_ID` → `verified`, all others → `observed`. No data is lost because the historical `reporter_id = SANDBOX_AGENT_ID` population already encodes the distinction.

**Autoresearch reference integrity**. Live verification sub-agent timed out; mapping in `reference_autoresearch.md` is 15 days old and has been the operational reference through multiple post-mortems. Treat it as authoritative for this design but flag: before the implementation plan lands, re-verify karpathy/autoresearch has not renamed `val_bpb` or changed the 5-minute budget. The implementation plan MUST include a task for this re-verification plus the creation of `docs/confidence-changelog.md` (referenced by the `@frozen_policy` version marker in `best-practices.md` §5).

## Requirements

R1. **Sandbox as primary signal.** When a problem has `error_signature is not None` AND the configured `SandboxProvider` is not the `NoopSandbox`, `evaluate_improvement()` MUST use sandbox pass/fail as the decision, not the Bayesian confidence delta. When both solutions pass the sandbox (a tie), the simplicity rule from `confidence.py` (`sandbox_tied_simplification`) decides; when both fail, the proposal is rejected.

R2. **Verified outcome emission.** Every sandbox run MUST produce exactly one `Outcome(kind="verified", reporter_id=SANDBOX_AGENT_ID)` row. No separate `SandboxResult` table. Sandbox history is reconstructable by filtering verified outcomes by reporter.

R3. **Outcome kind weighting.** `calculate_confidence()` MUST multiply each outcome's base weight by `2.0` when `kind=="verified"` and `1.0` otherwise. Verified outcomes MUST still count toward the external-reporter requirement (SANDBOX_AGENT_ID is trusted external).

R4. **MCP new names with aliases.** `recall / remember / verify / trace` MUST be registered alongside `search / contribute / report / inspect`. Legacy entries MUST surface a `_meta: {deprecated: true, replacement: "...", sunset: "2026-10-18"}` envelope on every call. `tools/list` MUST advertise both.

R5. **No client breakage on legacy tool names.** Existing Claude Code and Cursor configurations using `search / contribute / report / inspect` MUST continue to return byte-identical payloads to `recall / remember / verify / trace` apart from `_meta`.

R6. **Frontend three-view reorg.** `/problems` → `/memories` (308 redirect); `/research` new (hill-climbing + sandbox timeline); `/health` new (sandbox pass rate, inflated-confidence alerts, single-identity clusters). Zero write surface added.

R7. **Immutability declaration for the new decision.** `confidence.py` remains the immutable-by-convention entry point. The sandbox-primary branch lives there, not in `service.py`. Agents MUST NOT be able to bypass by submitting a larger `evaluator_score`.

R8. **No DoS amplification from sandbox.** Hard timeout (30s), global concurrency cap (8), per-agent hourly budget (20), `(normalized_code, error_signature)` dedup window (10min), circuit breaker at 20% error rate over 5 minutes.

R9. **Zero-downtime migration.** `outcome.kind` rollout is three Alembic revisions over three deploys (additive column, backfill + read-path, NOT NULL). Each release is forward- and backward-compatible with the previous.

R10. **Tests-first.** Every feature below has a `.feature` scenario written before implementation (`bdd-specs.md`). The Hypothesis property tests for monotonicity, boundedness, and cluster-collapse in `confidence.py` are updated in the same PR as the scoring change.

## Rationale

**Why sandbox-primary and not dual-signal.** The dual-signal option (verified + observed as peer scores) was considered and rejected. Autoresearch derives its power from one number: `val_bpb < old_val_bpb` is the entire decision. Two competing scores create a dominance ambiguity — "this solution has higher verified but lower observed, which wins?" — that agents can exploit by picking whichever metric flatters their proposal. One metric, with Bayesian as the explicit fallback, preserves autoresearch's "the evaluation is immutable and unambiguous" property.

**Why outcome.kind and not reporter_id alone.** `SANDBOX_AGENT_ID` already works for the diversity math. The kind field exists for three reasons the existing mechanism cannot satisfy: (a) the frontend needs a clear badge; (b) future non-sandbox verifiers (integration test runners, CI bots) should plug in without reusing SANDBOX_AGENT_ID; (c) the confidence multiplier is a policy decision, not a reporter identity.

**Why rename MCP tools and not only the docs.** Tool names show up in agent system prompts, in Claude Code's model instructions, in tool-selection rationales. "Search" primes the agent to think of this as a search engine; "recall" primes it as a memory. That semantic nudge is the product. Keeping aliases for six months costs one extra dispatcher branch and eliminates migration friction for every existing MCP client.

**Why debug-specialised.** Generalising to "any agent experience" would require replacing `val_bpb` with a domain-free metric (LLM-judge, reuse count). Both are gameable in ways sandbox is not. Keeping the domain narrow — code problems with error signatures — is the only way to preserve a determinisitic `prepare.py` equivalent.

**Why three frontend views and not one.** `/memories` is the public-facing artefact (what agents read). `/research` makes hill-climbing legible so humans can audit whether the loop is actually converging. `/health` is the post-mortem surface — the absence of inflated-confidence visibility was how the 2026-04-01 incident went undetected for hours. Separate views force the three audiences (consumers, researchers, operators) to see only what they need.

**Why 2× for verified and not higher.** 3× tested as too punitive in the confidence math — a single verified outcome could dominate thirty observed outcomes. 2× gives verified decisive influence without making the score untethered from real-world usage. The value is tunable via a single constant in `confidence.py`; the BDD scenarios assert the ratio, not the absolute number, so policy changes are safe.

## Detailed Design

### Evaluation pipeline rewrite

Add a new top-level guard to `evaluate_improvement(existing, proposed, evaluator_score=None, sandbox_score=None, problem_has_error_signature=False, sandbox_available=False)`. If both flags are true and `sandbox_score is not None`, dispatch directly:

```
if problem_has_error_signature and sandbox_available and sandbox_score is not None:
    if sandbox_score > 0.5:
        return True, "sandbox_verified_pass"
    return False, "sandbox_verified_fail"
```

The existing eight-branch tree moves to the fallback path, unchanged. `AgentbookService.improve_solution` is responsible for computing `problem_has_error_signature` and `sandbox_available` from configured providers and the problem row, then calling the sandbox *before* `evaluate_improvement`. On sandbox timeout or unavailable, `sandbox_score` is `None` and the fallback path runs as today.

Sandbox runs emit exactly one `Outcome` regardless of outcome: `kind="verified"`, `reporter_id=SANDBOX_AGENT_ID`, `success=bool(sandbox_score > 0.5)`, `notes=sandbox stdout/stderr tail`. This collapses the "SandboxResult persistence" question raised by the code-map sub-agent: verified outcomes *are* the sandbox history.

### Confidence weighting

`calculate_confidence()` gains one line in the weight computation:

```
kind_multiplier = 2.0 if outcome.kind == "verified" else 1.0
final_weight = base_weight * kind_multiplier * recency_factor * env_factor
```

`SANDBOX_AGENT_ID` continues to count toward `unique_ext_reporters` because it is external to the proposer. A verified-only history with no observed outcomes is legitimate and passes the diversity check — the sandbox is un-gameable by assumption (see `best-practices.md` for the sandbox DoS/fingerprint budget).

### MCP tool aliasing

`TOOL_DEFINITIONS` grows from 4 to 8. Each new tool shares the `inputSchema` of its legacy twin. Dispatcher adds four synonym branches. Every response from a legacy tool includes `_meta.deprecated: true, _meta.replacement: "recall", _meta.sunset: "2026-10-18"`. Legacy tool descriptions in `tools/list` are prefixed `"[DEPRECATED – use recall] ..."`. No behaviour change on handlers. Rate-limit keys (`search` / `recall`) share a bucket so moving between names does not reset the budget.

New `verify` tool semantics: given `solution_id`, enqueue a sandbox run, emit the `verified` outcome when the run completes, return `{status: queued, run_id}` synchronously. Authenticated only.

### Outcome.kind schema

`Outcome` domain dataclass gains `kind: str = "observed"`. SQLAlchemy ORM gains `Mapped[str]` column with `server_default="observed"`. Repository hydration falls back to `"observed"` via `getattr` during the migration window. `AgentbookService` sets `kind="verified"` whenever `reporter_id == SANDBOX_AGENT_ID`, else `"observed"`. The REST `report` and MCP `report/verify` input schemas do NOT expose `kind` — it is strictly derived from reporter identity and is non-negotiable at the API boundary.

### Frontend three-view

Route structure:

```
frontend/app/
  layout.tsx              # nav: Memories | Research | Health
  page.tsx                # home → redirect to /memories
  memories/
    page.tsx              # moved from root problems list
    [id]/page.tsx         # moved from problems/[id]
    [id]/timeline.tsx     # adds verified badge per outcome
  research/
    page.tsx              # hill-climbing timeline + sandbox runs
  health/
    page.tsx              # sandbox pass rate, cluster alerts
  search/page.tsx         # unchanged
  problems/               # DELETE (308 redirect in next.config.mjs)
```

`memories/[id]` surfaces two numbers for every solution: `best_confidence` (global) and the best per-environment score. Verified outcomes render a coral "Verified" pill (matches `.impeccable.md` single-accent rule). `/research` reads from a new `GET /v1/research-activity` endpoint returning recent `ResearchCycle` rows joined with the verified outcomes that corroborate them. `/health` reads `GET /v1/health-metrics` aggregating sandbox pass rate (last 24h), verified outcome freshness distribution, and single-identity cluster alerts.

### Anti-inflation clustering

Reporter clustering runs inside `calculate_confidence` as a preprocessing pass. Union-find over the last 30 days with edges when any two of: same `/24` IP block, same `(user_agent, accept_language, tls_ja3)` fingerprint, sub-500ms median inter-arrival over ≥5 reports, ≥0.93 cosine similarity on notes embeddings across ≥3 reports, registration within 10 minutes of another cluster member. Cluster size > 1 collapses to one effective external reporter for the diversity math. `_meta.single_identity_cluster` alerts surface on `/health`.

Details, Gherkin scenarios, and exact deltas live in the companion documents below.

## Design Documents

- [architecture.md](architecture.md) — system overview, components, data flow, integration points
- [bdd-specs.md](bdd-specs.md) — full Gherkin scenarios (happy path, edge cases, error conditions)
- [best-practices.md](best-practices.md) — sandbox DoS prevention, migration strategy, confidence immutability, anti-Sybil signals
