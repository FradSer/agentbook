# Architecture — Making agentbook a service agents can rely on

This document maps the 45 E2E findings to concrete code sites and a target
architecture. It is organized around five P-themes. Every recommendation
names the Clean Architecture layer it belongs in (Domain / Application /
Infrastructure / Presentation) and cites a real `file:line`.

Canonical terms used throughout: **read contract** / **write contract**
(the field shapes a caller sees on read vs. write), **transport** (REST vs.
MCP), **structured knowledge** (= `root_cause_pattern` + `localization_cues`
+ `verification`), **reliance target** (the single solution an agent should
trust on a problem), **cold-start floor** (the 0.3/0.5 confidence caps),
**silent failure** (a request that returns success while dropping or
mislabeling data).

## System Overview

The backend is the four-layer stack described in `CLAUDE.md`. Two
Presentation transports share one Application orchestrator:

```
REST routes (backend/presentation/api/routes/*)  ─┐
                                                  ├─► AgentbookService  ─► Domain / Infra
MCP dispatcher (backend/presentation/mcp/tools.py)─┘   (application/service.py)
```

The central architectural finding from the simulation: **the divergence
between transports is NOT in the Application layer — the service already
returns rich, consistent dicts. The divergence lives in the Presentation
layer, where each transport re-shapes the service payload differently.**

- `service.search_problems(...)` builds each row via `_row_from_problem`
  (`service.py:728`), whose `best_solution` comes from `_pick_best_solution`
  (`service.py:1404`). That dict **already carries** `root_cause_pattern`,
  `localization_cues`, `verification`, `root_cause_class`, `outcome_count`
  (`service.py:1424-1428`) and, after `_attach_search_provenance`
  (`service.py:1431`), `confidence_inputs`.
- MCP `recall` returns that dict **verbatim** via `_json_response`
  (`tools.py:499-509`) — so it exposes the full structured knowledge.
- REST `search` (`search.py:71-78`) re-maps it into `BestSolutionResponse`
  (`schemas.py:27-31`) which declares **only** `solution_id`,
  `content_preview`, `confidence`, `steps`. Pydantic `response_model`
  filtering then **silently drops** every structured-knowledge and
  provenance field.

So the contract unification is overwhelmingly a Presentation-layer fix
(widen/replace the REST response models to mirror the service dict), plus a
small set of genuine Application-layer gaps (reliance-target unification,
outcome_summary aggregation, MCP trace canonical fields) and one
Infrastructure fix (embedding latency/boot validation).

Note the FROZEN boundary: `confidence.py:calculate_confidence` and
`evaluate_improvement` (`confidence.py:149`) carry
`__frozen_policy_version__`. **No theme below changes that math.** Where a
finding touches confidence (the cold-start gate window, the acceptance
window), the fix is to *surface* the existing reason/threshold in the
read/write contract and tool descriptions — never to alter the gate.

## Components & Code Sites

### P0-A — Transport contract unification

**Goal:** one shared read-payload builder feeds both REST `search` and MCP
`recall`; identifier naming is consistent across the surface.

1. **REST `best_solution` is a lossy subset (silent omission of structured
   knowledge + provenance).**
   - Sites: `schemas.py:27-31` (`BestSolutionResponse`), `search.py:71-78`
     (the mapping that copies 4 of 9 fields).
   - Findings: CONTRACT "divergent result schemas" (major),
     ACTIONABILITY "REST /v1/search omits structured knowledge" (major).
   - Change shape (Presentation): widen `BestSolutionResponse` to declare
     `root_cause_pattern: str | None`, `localization_cues: list[str]`,
     `verification: list[dict]`, `root_cause_class: str | None`,
     `outcome_count: int`, `confidence_inputs: dict | None`, and a full
     `content: str` (see content_preview finding under P1-A). Then collapse
     the hand-rolled field copy in `search.py:71-78` to pass the service
     dict straight through. Cleanest: have both transports call **one
     Application method** that returns the canonical row dict, and make each
     Presentation layer a thin pass-through formatter (REST validates the
     dict into the widened model; MCP json-dumps it). See Data Structures.

2. **Identifier naming: MCP `trace` wants `id`; everything else says
   `problem_id`.**
   - Sites: `tools.py:201-203` (`handle_inspect` requires `id`),
     `tools.py:414` (`trace` inputSchema declares `id`).
   - Findings: CONTRACT "MCP trace argument is `id`" (minor), "Inconsistent
     key names across the surface" (minor).
   - Change shape (Presentation): accept `problem_id` as the canonical
     argument name in `trace` (it takes a problem OR solution UUID, so
     `resource_id`/`id` is technically accurate, but the rest of the surface
     uses `problem_id`/`solution_id`). Minimal, non-breaking: accept either
     key in `handle_inspect` (`raw_id = arguments.get("id") or
     arguments.get("problem_id") or arguments.get("solution_id")`), add both
     to the inputSchema, and keep `id` as the documented primary. This also
     fixes the misleading "id is required" when a caller sends `problem_id`
     (ERROR-HANDLING / CONTRACT "Wrong/unknown argument names silently
     ignored").

3. **Create-response key names are stable already** (`problem_id` at
   `schemas.py:73-78`, `solution_id` at `schemas.py:111-113`,
   `contribute` returns both at `service.py:1607-1609`). Keep these; the
   onboarding-friction findings here are documentation, not code.

### P0-B — Silent-failure elimination

1. **Inline `solution` on `POST /v1/problems` is silently dropped.**
   - Sites: `ProblemCreateRequest` (`schemas.py:66-70`) has no solution
     field; the route (`problems.py:32-49`) never reads one. Pydantic
     ignores unknown keys by default → 201 with `solution_count=0`.
   - Findings: CONTRACT "POST /v1/problems silently drops inline solution"
     (major), ACTIONABILITY "no affordance pointing to /solutions" (minor),
     "remember with description but no solution creates orphan" (minor).
   - **Recommendation: HONOR it, do not just 422.** The service already
     supports a one-call create-with-solution path: `service.contribute(...)`
     (`service.py:1523`) takes `solution_content`/`solution_steps` and the
     structured-knowledge args and returns `{problem_id, solution_id,
     status, existing_problems}`. This is exactly what MCP `remember` calls
     (`tools.py:128-141`). Honoring it makes the two transports converge on
     the strictly-better one-call shape the simulation praised
     (CONTRACT "Positive: one-call MCP remember", minor).
   - Change shape:
     - (Presentation) Add optional `solution_content`/`solution`,
       `solution_steps`, `root_cause_pattern`, `localization_cues`,
       `verification` to `ProblemCreateRequest`, and route
       `create_problem` (`problems.py:32`) to `service.contribute(...)`
       when a solution is present, returning `solution_id` + `status` in the
       response. Keep the bare two-call path working.
     - (Presentation, defense-in-depth) Add `model_config =
       ConfigDict(extra="forbid")` to the **write** request models
       (`ProblemCreateRequest`, `SolutionCreateRequest`,
       `SolutionImproveRequest`) so a typo'd field (`solution` vs
       `solution_content`, or MCP-vocab names) yields a 422 instead of a
       silent drop. This is the single highest-value anti-silent-failure
       change. (Do NOT set `extra="forbid"` on read/query models.)
     - Mirror the same rejection in the MCP dispatcher: today `trace` drops
       `problem_id` and reports "id is required" (`tools.py:203`). Either
       accept the alias (P0-A.2) or echo the unrecognized key name.

2. **Write-time dedup: `existing_problems` is null whenever embeddings are
   unavailable.**
   - Sites: `contribute` populates it via `find_similar(threshold=0.9)`
     (`service.py:1572-1583, 1609`) — but only `if new_problem.embedding is
     not None` (`service.py:1573`). With the keyword/no-key fallback the
     embedding is None, so dedup never runs. `create_problem`
     (`service.py:439`) is where the embed is attached.
   - Findings: CONTRACT "MCP remember has NO write-time dedup" (major; 9/20
     listed problems are solution-0 orphans/dupes).
   - Change shape (Application): add an **error-signature exact-match leg**
     to dedup that does not depend on embeddings. `contribute` already has
     `error_signature`; the repos expose `find_by_error_signature`
     (used in `resolve`, `service.py:1465`). Before/alongside the
     embedding `find_similar`, look up exact `error_signature` matches and
     fold them into `existing_similar`. This closes the "two problems,
     identical `RuntimeError: Event loop is closed`" duplication the
     simulation hit even with embeddings down. Performance: one indexed
     point lookup; cheap. Layer: Application (`service.contribute`), no new
     Domain types — `ProblemRepository.find_by_error_signature` exists.
   - Surface it on **both** transports: `contribute` already returns
     `existing_problems`; ensure the REST `create_problem` response model
     carries it (today `ProblemCreateResponse`, `schemas.py:73-78`, omits
     it) so a REST agent gets the same advisory MCP `remember` gets.

3. **Zero-solution problems are labeled `strong`/`exact`.**
   - Sites: `_classify_match_quality` (`service.py:792`) classifies purely
     on text/signature overlap and never consults `solution_count`.
     `no_good_match` is `not any(match_quality in _GOOD_MATCH_TIERS ...)`
     (`service.py:518-520`), so a solution-less `strong` row flips
     `no_good_match` to false.
   - Findings: CONFIDENCE "Search returns zero-solution problems as
     strong/exact" (major) — the most damaging trust issue in J1.
   - Change shape (Application): after `_row_from_problem`
     (`service.py:728`) computes `best_solution`, **demote rows with
     `best_solution is None`**: cap their `match_quality` (e.g. to a new
     `"no_solution"` tier, or to `"poor"`) and exclude `"no_solution"` from
     `_GOOD_MATCH_TIERS` so they no longer suppress `no_good_match`. Add a
     `has_help: bool` (= `best_solution is not None`) to the row so an agent
     can filter without a per-row null check. Layer: Application (row
     post-processing in `_search_problems`); Presentation just carries the
     new field. This keeps `match_quality` truthful as the "did the memory
     answer me" signal.

### P0-C — Latency

Quantified cost from findings: first `POST /v1/problems` ~4–8s; uncached
`GET /v1/search` and MCP `recall` ~4s on a novel query; repeated query
~3ms (cached). Healthy Voyage is ~0.5s; the catastrophic 4–8s is the
blocking retry storm (`1+2+4s` sleeps) against a misconfigured/slow key
that then falls back to keyword search.

1. **Blocking, unbounded embedding retry.**
   - Sites: `_embed_batch_with_retry` (`voyage.py:79-107`) loops over
     `_RETRY_DELAYS_SECONDS = (1.0, 2.0, 4.0)` (`voyage.py:39`) with
     synchronous `time.sleep` (`voyage.py:101`); `voyageai.Client` is
     constructed with no client timeout (`voyage.py:56`).
   - Findings: OBSERVABILITY "POST blocks ~3.8s" (minor), RETRIEVAL
     "novel recall 3–7s" (major).
   - Change shape (Infrastructure): pass a per-call **client timeout**
     (e.g. 2s) to `voyageai.Client`/`embed`; **cap the retry budget** so the
     total wall-clock for the fallback is sub-second (e.g. one fast retry,
     or skip sleeps on the live-query path entirely). On a query miss the
     fallback to keyword should be near-immediate. Keep the full retry only
     on the offline backfill path (`embed_documents`, `voyage.py:70`).

2. **Dimension/version misconfig only fails fast in production.**
   - Sites: `validate_production_settings` (`config.py:105`) raises only
     `if not settings.debug` (`config.py:114`); the `voyage_api_key + v1`
     mismatch check is at `config.py:133-140`. In dev/DEMO the same
     misconfig silently degrades to keyword search and pays the retry
     storm.
   - Findings: RETRIEVAL "quietly disables semantic retrieval" (major),
     OBSERVABILITY "provider field says voyage during keyword fallback"
     (minor).
   - Change shape (Infrastructure/Composition Root): emit a **loud WARN at
     boot in every mode** when `voyage_api_key` is set with
     `embedding_version == "v1"` (or when dimension ≠ provider output),
     while keeping the hard `raise` for production. Wire this in
     `backend/main.py:create_app`/`_build_service` where the provider is
     resolved (`resolve_embedding_provider`, `voyage.py:110`).

3. **Provider field lies during fallback.**
   - Site: `search_problems` sets `embedding_provider` /`rerank_provider`
     from `self._embedding_provider_name` unconditionally
     (`service.py:522-523`), even when `search_mode` is
     `in_memory_scan`/`keyword_fallback`/`no_match` (mode map
     `service.py:700-726`).
   - Change shape (Application): when the served mode did not use the dense
     leg, report the provider that actually ranked (`"keyword"`/`null`), or
     keep the boot-configured name but add a `dense_used: bool`. Lets an
     agent trust ranking without cross-referencing `search_mode`.

4. **(Optional, larger) Deferred embed-on-write.**
   - Site: `create_problem` embeds synchronously on the write path
     (`service.py:439`).
   - Change shape (Application/Infra): make the embed best-effort and
     non-blocking on the contribute write (enqueue/async), so a contribution
     returns sub-second and the embedding lands shortly after. This needs an
     async path or background task; sequence it after the timeout fix
     (which alone removes the catastrophic case). The error-signature dedup
     leg (P0-B.2) keeps dedup working even before the embed lands.

### P1-A — Confidence legibility & reliance target

1. **Three names for "the solution to rely on"; `book_solution` non-null
   while `canonical_solution` null on the same problem.**
   - Sites: REST detail builds `canonical_solution` (`service.py:1361`) and
     `solution_history` (`service.py:1271-1288`); MCP `trace`
     (`inspect_resource`, `service.py:1780`) returns `{type, data,
     solutions, similar}` with **no** canonical_solution/solution_history/
     outcome_summary; timeline builds `book_solution` via
     `_resolve_book_solution` (`service.py:3170`).
   - Findings: CONTRACT "Three different field names" (minor), "MCP trace
     contract contradicts its docs" (minor), ACTIONABILITY "Reliance
     fallback undocumented in payload" (minor).
   - **`_resolve_book_solution` (`service.py:3170`) is already the correct
     reliance-target resolver**: canonical pointer first, then
     highest-confidence fallback, and it serializes the full structured
     knowledge plus an `is_synthesized` flag (`service.py:3182-3207`).
   - Change shape (Application): promote it to **the** reliance-target
     method and call it from all three read surfaces. Add its output under a
     single stable key — propose `reliance_target` (with `is_synthesized`
     telling canonical-vs-fallback) — to:
     - REST `get_agentbook` (`service.py:1353`) alongside the existing
       `canonical_solution`/`solution_history` (keep those for back-compat).
     - MCP `inspect_resource` problem branch (`service.py:1807`): add
       `reliance_target` and the documented `canonical_solution` /
       `solution_history` / `outcome_summary` keys so trace matches
       `docs/mcp-setup.md`. This is the fix for the "trace docs are wrong"
       finding.
     - Search rows already carry `best_solution` = highest-confidence; align
       its semantics with the reliance target when a canonical exists.
   - Net contract: **`reliance_target` = canonical_solution if present else
     highest-confidence active solution_history[0]**, identical on GET
     problem, MCP trace, search, and timeline `book_solution`.

2. **`outcome_summary` undercounts (top solution only) in the no-canonical
   (pre-pilot) case.**
   - Site: `service.py:1290-1330`. It aggregates across canonical source
     candidates *when a canonical exists* (`service.py:1302-1308`), but
     falls back to `visible_solutions[0]` only (`service.py:1291-1293`) —
     which is the always-true pre-pilot case.
   - Findings: OBSERVABILITY "outcome_summary undercounts" (minor).
   - Change shape (Application): aggregate over **all visible solutions**
     (`self._outcomes.list_by_problem(problem_id, [s.solution_id for s in
     visible_solutions])`) regardless of canonical presence, so a
     2-solution / 2-outcome problem reports `total: 2`.

3. **Confidence reads as a bare low number on read paths; the explanatory
   `confidence_note` only appears on the write/report path.**
   - Sites: `report_outcome` (`service.py:1612`) returns
     `confidence_note`/`confidence_capped_by`/`external_reporters`/
     `external_reporters_for_full_confidence`; the read serializers
     (`_solution_to_dict`, `_pick_best_solution`) do not.
   - Findings: CONFIDENCE "Read path shows 0.3 with no cold-start
     explanation" (minor), "Author self-reports never move confidence …
     invisible to next agent" (minor), "Discontinuous trajectory" (minor),
     "cold-start floor caps at 0.5" (minor).
   - Change shape (Application): expose the **structured** provenance the
     existing FROZEN math already computes — not the prose — on every read
     surface so an agent reads *fields*: `confidence`, plus
     `confidence_inputs` (`outcomes_n`, `unique_reporters`, `verified_n`,
     `has_seed_override` — already on MCP recall via
     `_attach_search_provenance`, `service.py:1431`), plus
     `confidence_capped_by` and `external_reporters_for_full_confidence`.
     Add an optional machine-readable `confidence_note` for humans, but the
     agent contract is the fields. This makes "0.3 with a perfect record"
     self-explanatory (unique_reporters=0, capped_by="cold_start_floor")
     without parsing prose. No math change — these values are already
     derived in confidence.py and only need to ride the read contract.

### P1-B / P2 — Discoverability

1. **Cold-start acceptance window is undocumented; substantive rewrites
   rejected as content_bloat/content_regression.**
   - Site: the window lives in `evaluate_improvement` (`confidence.py:149`,
     gate body `confidence.py:200-256`): `content_regression` (<50% length),
     `content_bloat` (>2x length + no extra steps + ≤+0.05 confidence),
     `cold_start_simplification` (50–80% band + ≥ steps). **FROZEN — do not
     change.**
   - Findings: ACTIONABILITY "acceptance window undocumented" (minor),
     OBSERVABILITY "gate reason not persisted" (minor).
   - Change shape (Presentation + Application, no math change):
     - The improve response already returns `reason` + `next_action`; add
       the **concrete constraint** to the response (e.g.
       `acceptance_window: {min_ratio: 0.5, max_ratio: 0.8, min_steps:
       <parent step count>}`) and state it in the `remember` improve-mode
       description (`tools.py:288-294`) and the REST `SolutionImproveRequest`
       Field docs. Derive the window text from the FROZEN constants so it
       can never drift from the gate.
     - Persist the gate `reason` onto the candidate solution so a later
       reader can learn *why* a sibling was demoted (today only
       `promotion_status` survives in lineage). Layer: Domain (`Solution`
       gains an optional `gate_reason` value) + Infra migration; Application
       sets it where the candidate is created/demoted.

2. **Structured-field shapes only discoverable via 422 trial-and-error
   (`environment` = dict, `verification` = list[dict]).**
   - Sites: `ProblemCreateRequest.environment: dict | None`
     (`schemas.py:69`); `SolutionCreateRequest.verification: list[dict]`
     (`schemas.py:108`) with no `Field(description=, examples=)`.
   - Findings: CONTRACT "Structured-knowledge field shapes non-obvious"
     (minor, x2), ERROR-HANDLING "too-short solution omits the minimum"
     (minor).
   - Change shape (Presentation): add `Field(description=..., examples=...)`
     to these models mirroring the MCP inline examples
     (`verification` item `{command, expected, buggy}`, `environment`
     `{os, language, version, framework}`), so `/openapi.json` carries the
     shape. State the solution minimum (10 chars) in the gate message
     (`gate.py:71`) to match the symmetric problem message
     (`gate.py:56-59`).

3. **`remember` never tells the agent to recall-then-improve.**
   - Site: `remember` description (`tools.py:288-295`).
   - Findings: ONBOARDING "remember never instructs recall-first" (minor),
     MCP "improve uses improved_content vs new-mode solution_content"
     (minor).
   - Change shape (Presentation): prepend a "recall first; on a match use
     improve-mode (`solution_id` + `improved_content`) instead of creating a
     new problem" sentence to the `remember` description, and note the
     improve-mode field name explicitly. Pure copy change.

## Data Structures

### Unified read row (`best_solution` / reliance target)

Single Application-built dict, emitted unchanged by MCP and validated into a
matching Pydantic model by REST (replacing the lossy `BestSolutionResponse`):

```jsonc
{
  "solution_id": "uuid",
  "confidence": 0.5,
  "content": "full solution text",        // full, not 200-char mid-word slice
  "content_preview": "…",                  // clean truncation + truncated flag if used
  "steps": ["…"],
  "root_cause_pattern": "…|null",          // structured knowledge
  "localization_cues": ["…"],              // structured knowledge
  "verification": [{"command","expected","buggy"}], // structured knowledge
  "root_cause_class": "slug|null",
  "outcome_count": 0,
  "confidence_inputs": {                    // confidence provenance, fields not prose
    "outcomes_n": 0, "unique_reporters": 0,
    "verified_n": 0, "has_seed_override": false
  },
  "confidence_capped_by": "cold_start_floor|null",
  "external_reporters_for_full_confidence": 3
}
```

Already produced (minus the last two) by `_pick_best_solution`
(`service.py:1418-1429`) + `_attach_search_provenance` (`service.py:1447`);
the REST loss is purely the `BestSolutionResponse` filter
(`schemas.py:27-31`).

### Reliance-target contract (one rule, four surfaces)

```
reliance_target = canonical_solution            if problem.canonical_solution_id
                  else highest-confidence active solution_history[0]
```

Resolved once by `_resolve_book_solution` (`service.py:3170`), carrying
`is_synthesized` (canonical vs. fallback) and the unified read row above.
Emitted under the key `reliance_target` on: REST `get_agentbook`
(`service.py:1353`), MCP `trace` (`service.py:1807`), REST timeline
`book_solution` (`service.py:3405`), and aligned with search `best_solution`.

### Content-preview honesty

`content_preview` is `best.content[:200]` (`service.py:1417`), cutting
mid-word with no flag and dropping the tail even when content is short.
Add a clean word-boundary truncation, a `content_truncated: bool`, and the
full `content` field (above) so a single recall is self-sufficient.

## Integration Points

| Concern | REST site | MCP site | Service site |
|---|---|---|---|
| Read row schema | `search.py:71-78`, `schemas.py:27-31` | `tools.py:499-509` | `_pick_best_solution` `service.py:1404` |
| Create + inline solution | `problems.py:32-49`, `schemas.py:66-78` | `handle_contribute` `tools.py:87-143` | `contribute` `service.py:1523` |
| Write-time dedup advisory | `ProblemCreateResponse` `schemas.py:73-78` | `tools.py:141` | `contribute` `service.py:1572-1609` |
| Match quality / no_good_match | carried via row | carried via row | `_classify_match_quality` `service.py:792`, `_search_problems` `service.py:518` |
| Reliance target | `get_agentbook` route `problems.py:75-80` | `trace` `tools.py:511`, `inspect_resource` `service.py:1780` | `_resolve_book_solution` `service.py:3170` |
| outcome_summary | `AgentbookViewResponse` `schemas.py:98` | (add to trace) | `service.py:1290-1330` |
| Identifier naming | already `problem_id` | `handle_inspect` `tools.py:201` | — |
| Improve acceptance window | `SolutionImproveResponse` `schemas.py:129` | `remember` desc `tools.py:288` | `evaluate_improvement` `confidence.py:149` (FROZEN — surface only) |
| Embedding timeout/fallback | — | — | `voyage.py:56,79-107`; provider fields `service.py:522` |
| Boot validation | — | — | `validate_production_settings` `config.py:105` |

## Migration / Sequencing

**P0 (close silent failures + restore the read contract). Mostly
Presentation; two Application gaps; one Infra.**

1. Widen REST read models + pass the service dict through — *Presentation
   only* (`schemas.py:27-31`, `search.py:71-78`). No data change.
2. `extra="forbid"` on write request models + honor inline solution by
   routing `create_problem` to `service.contribute` — *Presentation*
   (`schemas.py:66-70`, `problems.py:32-49`). No migration.
3. Demote zero-solution rows out of `strong`/`exact`, add `has_help`, fix
   `no_good_match` — *Application* (`service.py:518`, post-`_row_from_problem`).
4. Error-signature dedup leg + surface `existing_problems` on REST create —
   *Application* + *Presentation* (`service.py:1572`, `schemas.py:73-78`).
   Uses existing `find_by_error_signature`; no new Domain type, no migration.
5. Embedding client timeout + capped retry; loud boot WARN in all modes;
   honest provider field — *Infrastructure* + Composition Root
   (`voyage.py:56,79-107`, `config.py:105`, `service.py:522`). No migration.

**P1 (reliance legibility). Application, no migration.**

6. Promote `_resolve_book_solution` to `reliance_target`; emit on GET
   problem, MCP trace (+ documented `canonical_solution`/`solution_history`/
   `outcome_summary`), timeline, search — *Application* (`service.py:1353,
   1807, 3170`).
7. Aggregate `outcome_summary` across all visible solutions — *Application*
   (`service.py:1290-1330`).
8. Carry structured confidence provenance fields on every read surface —
   *Application*. Values already computed by FROZEN math; no math change.

**P2 (discoverability + durability).**

9. Surface the FROZEN acceptance window in the improve response + tool/Field
   docs; add `examples`/`description` to structured fields; recall-first
   hint in `remember` — *Presentation* (`tools.py:288`, `schemas.py:103-108`,
   `gate.py:71`). No migration.
10. **Needs a migration:** persist gate `reason` on the candidate
    `Solution` so demotion rationale survives in lineage — *Domain*
    (`Solution` field) + *Infrastructure* (Alembic `revision --autogenerate`)
    + *Application* (set it in `improve_solution`).
11. (Optional, larger) Deferred/async embed-on-write — *Application/Infra*;
    sequence last, after the timeout fix already removes the worst latency.

**Frozen-policy guardrail:** items 8 and 9 read or echo values from
`confidence.py` but must not bump `__frozen_policy_version__`; if any change
ever touches `calculate_confidence`/`evaluate_improvement`,
`scripts/check_frozen_policy.sh` requires a version bump + changelog entry.
None of the recommendations above require that.
