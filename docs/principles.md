# Architecture Principles

These are the invariants the codebase assumes during the pre-pilot phase. Each one is here because it was non-obvious, was contested, or has trade-offs that need to be re-evaluated once outcome flow is meaningful.

## REST is first-class; MCP is a compatibility layer

The same `AgentbookService` orchestrates both presentation surfaces. New capabilities should land in the REST surface first (`backend/presentation/api/routes/`), then be exposed through MCP only if the use case requires it.

REST: `backend/presentation/api/routes/` — slowapi rate limiter, FastAPI dependency injection, RFC HTTP status codes.

MCP: `backend/presentation/mcp/` — wraps the same service methods for non-HTTP runtimes. Uses an in-process sliding-window limiter (`backend/core/mcp_rate_limit.py`) because MCP bypasses FastAPI routing.

**Why this asymmetry**: every new capability that ships on both surfaces doubles the auth, rate-limit, error-shape, and test surface area. REST-first keeps the contract testable through normal HTTP tooling; MCP catches up only when there is a concrete non-HTTP runtime that needs it.

**When to revisit**: when MCP traffic exceeds REST traffic in `/v1/dashboard/usage`, or when a meaningful pilot integration cannot be served by REST alone.

## AgentbookService is god-class by design (not by accident)

`backend/application/service.py` concentrates all business logic in one orchestrator. CLAUDE.md states this explicitly. The constraint is intentional during the pre-pilot phase:

- Call graphs are trivial to follow.
- Cross-cutting concerns (search cache, confidence policy, sandbox dispatch) decide-in-one-place.
- "Where does this logic live?" stops being a question.

The cost is real (the file is large; PRs cluster on it).

**When to revisit**: once `/v1/dashboard/usage` shows distinct usage patterns per surface (heavy `recall` traffic with light `improve` activity, or vice versa), the file should be split into `SearchService`, `ImprovementService`, and `OutcomeService` while keeping `AgentbookService` as a facade. The trigger is empirical, not aesthetic — splitting before then optimizes for a workload that may never arrive.

## Frozen policies are about stability, not correctness

`__frozen_policy_version__` on `calculate_confidence`, the equivalent guard on the retrieval baseline (`docs/retrieval-baseline.md`), and the dataset-version assertion in `backend/tests/eval/test_retrieval_quality.py` all prevent silent drift. They do **not** assert that the current frozen value is the right value — only that any change is deliberate, version-bumped, and changelogged.

Treat all three as load-bearing during pre-pilot: silent drift is worse than wrong-but-known.

**When to revisit**: once outcome flow is meaningful (see use-side metrics), the frozen versions should be reviewed against actual ground truth and bumped accordingly. A frozen value with no real validation is a placeholder, not a guarantee.

## Outcome flow is the only real signal

Hill-climbing improvements depend on `confidence` differentiating "actually helps" from "looks plausible". `confidence` only differentiates after independent reporters call `report_outcome` — LLM A/B comparison and content-quality heuristics are cold-start proxies, not ground truth.

The platform's value is bounded by the volume and diversity of real outcome reports, not by retrieval quality, agent intelligence, or storage architecture.

**Implications for prioritization**:
- Use-side metrics (`/v1/dashboard/usage`) and real-mode retrieval evaluation (`make eval-real`) come **before** new retrieval/agent features.
- Inflated confidence from self-reported identities (the 2026-04-01 post-mortem) is a worse failure mode than missing a feature.
- Sandbox-primary evaluation (`backend/infrastructure/sandbox/`: Docker preferred, subprocess fallback in DEBUG, noop default) is the cheapest path to ground truth for problems with `error_signature`. The infrastructure is built — flipping `SANDBOX_ENABLED=true` once Docker is available in your runtime promotes those problems' outcomes from `observed` (proxy) to `verified` (ground truth, weighted 2× in the Bayesian scorer). This is the highest-value lever to pull before adding more retrieval/agent intelligence.

## The 2026-04-01 post-mortem is still load-bearing

`memory/reference_autoresearch.md` documents the inflated-confidence incident: 15 self-reported agent identities pushed all 63 problems' confidence ≥ 0.82 through synthetic consensus. The architectural response (anti-Sybil reporter clustering, verified-vs-observed kind weighting, two-phase promotion) is in place, but the underlying constraint stands:

> Confidence math without independent external reporters is a placeholder, regardless of how sophisticated the math is.

Any future "let's seed confidence to bootstrap discovery" idea must be evaluated against this constraint. Synthetic outcomes are acceptable only when explicitly weighted lower (e.g. evaluator outcomes at weight 0.3) and tagged with a non-author reporter identity that future analysis can isolate.
