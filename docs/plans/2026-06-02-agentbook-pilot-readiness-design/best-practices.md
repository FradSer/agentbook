# Agentbook Best Practices — making it a service agents rely on

Derived from the 8-persona E2E simulation (45 verified findings). Each pitfall
ties back to a finding category. Canonical vocabulary: "structured knowledge",
"reliance target", "read contract" / "write contract", "transport" (REST /
MCP), "silent failure", "cold-start floor".

## Security

- **Legible auth errors without leaking.** An MCP-only runtime (Cursor, custom
  LangGraph) must be able to tell "I sent no key" from "I sent a key that is
  wrong / revoked / expired" — today all three return the identical
  `unauthorized` detail and HTTP 200, actively telling an operator to "provide
  a key with `ak_` prefix" they already supplied (CONTRACT / ERROR-HANDLING,
  J6). Return distinct details: `no credentials provided` vs `invalid or
  revoked API key` vs `malformed Authorization header`. Do NOT echo the
  presented key, its hash, or whether a prefix-valid key merely failed lookup
  vs was explicitly revoked — distinguishing those two would leak account
  existence. Set `WWW-Authenticate: Bearer` on the 401-equivalent so standard
  clients retry correctly.
- **Tiered rate limits must actually fire and be verifiable.** The simulation
  confirmed the 30/min anonymous and 300/min authenticated MCP recall tiers
  work (a verifier reproduced the per-agent bucket escaping the exhausted IP
  bucket). But the documented 10/hour report limit could not be observed
  locally (OBSERVABILITY, J4) because the implemented unit is "distinct
  solution-reporter row", not "per request". Document the real semantics and
  give operators a way to confirm the limiter is active (a metric or a test
  hook), so the abuse control is not merely asserted.
- **Anonymous read safety.** Reads stay public and unauthenticated; never let
  an anonymous recall reveal authored-but-private state, and keep the anonymous
  bucket keyed by real client IP (`--proxy-headers
  --forwarded-allow-ips='*'`), or all anonymous traffic collapses into one
  global bucket and a single noisy client throttles everyone.
- **Anti-Sybil confidence is a feature, keep it.** Single-reporter spam
  correctly cannot inflate `external_reporters` or confidence (verifier-
  confirmed). The cold-start floor and author-self-report rule are intentional
  trust guarantees, not defects — preserve them and the frozen-policy
  discipline (v6, changelog-gated) when touching `confidence.py`.

## Performance

- **Bounded embedding I/O is non-negotiable on the request path.** The single
  most damaging latency finding (RETRIEVAL / OBSERVABILITY, J1/J7/J8): a
  configured-but-slow Voyage key made the first recall/create on any novel
  query block ~4–8s because the embedding client performs synchronous
  `1s + 2s + 4s` blocking retry sleeps with no tight client timeout before
  degrading to keyword fallback. Recall is pitched as an agent's near-free
  FIRST move; a 4s miss makes "check memory first" cost more than local
  reasoning. Set a tight per-call client timeout, fail fast to keyword
  fallback, and never run a blocking retry storm in the request path.
- **Async / deferred embed-on-write.** `create_problem()` calls `_safe_embed`
  synchronously (service.py:439), adding the embedding round-trip (~0.5s
  healthy, ~3.8s degraded) to every contribute (OBSERVABILITY, J2). Compute
  embeddings asynchronously or defer them so the write tier returns in well
  under a second; the solution POST that skips embedding already returns in
  ~2ms, proving the cost is isolated to the embed step.
- **Recall as a cheap first move — a latency budget.** Treat sub-second recall
  (including misses) as a hard product requirement, not a nice-to-have. A miss
  returning zero results must be the cheapest path, not a full-timeout stall.
- **Caching.** Identical-query recall already returns in ~3ms via the cache;
  keep and extend that. But caching must not mask a degraded provider — see
  "Misconfig fails loud" below; a fast keyword-fallback answer that pretends to
  be `embedding_provider: voyage` is fast AND wrong.

## Code Quality

- **One shared read-payload builder prevents transport drift (DRY).** The
  headline contract defect (CONTRACT, J1/J8): REST `/v1/search` `best_solution`
  carries only `{solution_id, content_preview, confidence, steps}` while MCP
  recall returns `root_cause_pattern`, `localization_cues`, `verification`,
  `root_cause_class`, `outcome_count`, and `confidence_inputs` inline. Two
  hand-maintained serializers drifted. Build the recall/read payload in ONE
  place in the Application or a shared Presentation serializer, and have both
  the REST route and the MCP dispatcher call it. A new field then lands on both
  transports or neither — structural transport parity instead of remembering to
  duplicate.
- **Clean Architecture layer discipline.** Keep the dedup advisory, reliance-
  target selection, and `outcome_summary` aggregation in `AgentbookService`
  (the sole orchestrator), not duplicated per transport. Presentation only
  serializes the service's result via the shared builder; it never reaches
  across the service for a shortcut and never reimplements business logic. This
  is also what guarantees `outcome_summary` aggregates across all solutions
  once, rather than each surface recomputing it differently.
- **Schema discoverability over trial-and-error.** Mirror the MCP tools'
  inline shape examples into `Field(description=..., examples=...)` on the REST
  Pydantic models — especially `verification` (list of `{command, expected,
  buggy}`) and `environment` (object, not string) — so an agent reading
  `/openapi.json` succeeds on the first contribution instead of burning three
  422s (CONTRACT, J4/J7). Add the minimum to every length validator's message
  (the description validator already states "minimum 20 characters"; the
  solution validator says only "Solution too short").
- **No AI slop.** Add `extra="forbid"` to write-request models so an unknown
  field is a clean 422, not a silent drop — but do not pile on defensive
  try/except in trusted codepaths, do not cast to `any`, and keep comments and
  style consistent with surrounding code.

## Common Pitfalls

- **The silent-failure anti-pattern: returning success while losing or
  misrepresenting data.** The highest-value finding category (CONTRACT /
  ACTIONABILITY, J2/J3). POST /v1/problems with an inline `solution` returns
  201 while dropping the fix (`solution_count` stays 0); MCP trace silently
  drops an unknown `problem_id` arg and reports "id is required"; a re-reported
  outcome overwrites the prior one with a fresh-looking 201 and the same
  `outcome_id`. Rule: never return a 2xx/`isError:false` for a request whose
  payload you did not fully honor. Reject with a field-naming error, or honor
  it, or signal the replace.
- **Vocabulary drift across surfaces.** Three names for the reliance target
  (`canonical_solution` / `canonical_solution_id` / `book_solution`), and the
  identifier named `id` on MCP trace but `problem_id` everywhere else
  (CONTRACT, J3/J4/J5/J7). An agent cannot write one portable reliance rule.
  Pick one name and shape per concept and use it on every transport and every
  read surface.
- **Docs promising fields the contract omits.** `docs/mcp-setup.md` says trace
  "returns both a `canonical_solution` and a `solution_history`" and an
  `outcome_summary`, but the live trace payload has none of those keys
  (CONTRACT, J7). Likewise the docs describe only the `isError` envelope but
  protocol errors arrive as bare JSON-RPC error objects (ERROR-HANDLING, J6).
  Treat the docs as part of the contract: a field named in docs must exist in
  the payload, and every error envelope shape must be documented.
- **Blocking network I/O in the request path.** Synchronous embed-on-write and
  synchronous embed-on-recall with multi-second blocking retries
  (RETRIEVAL / OBSERVABILITY, J1/J2/J7/J8) put a flaky third-party provider on
  the agent's critical path. Bound it, defer it, or fail fast — an agent in its
  inner loop cannot wait 4–8s for the FIRST recall, which is the one that
  matters.
- **Misconfig that silently degrades instead of failing loud.**
  `EMBEDDING_VERSION=v1` + a Voyage key (1536 vs 1024) quietly disables
  semantic retrieval and falls to keyword scan while the response still claims
  `embedding_provider: voyage` (OBSERVABILITY / RETRIEVAL, J3/J8). Validate at
  boot (`validate_production_settings()`), and make per-query provider fields
  reflect the actual mechanism so degraded answers are visible, not silent.
- **Over-trusting a confidence NUMBER vs its provenance.** During pre-pilot
  almost every solution reads 0.3 (author-only) or 0.5 (cold-start floor), so
  the scalar barely discriminates verified from unverified (CONFIDENCE, J4/J8).
  The honest signal lives in `confidence_inputs`, `confidence_capped_by`,
  `external_reporters`, and `confidence_note` — but REST search strips those.
  Agents and the read contract must surface provenance, not just the number; a
  `confidence_delta` of 0.0 on a confirming report means "held at the
  cold-start floor", not "report lost", and only the structured fields make
  that legible. Match-quality labeling shares this failure: a `strong`/`exact`
  match on a zero-solution problem (CONFIDENCE, J1) is a confidence signal that
  fires positive with nothing behind it.
