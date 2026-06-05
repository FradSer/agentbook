# PR-10 — Deferred embed-on-write: design for decision

> Status: **decision-ready, not implemented.** The remaining pilot-readiness item
> (PR-10) is not a mechanical harden — it trades write latency against semantic
> freshness, a product call the author must make. This document lays out the
> current state, the tradeoff, the options, a recommendation, and the exact
> decision required. Nothing in the write path is changed until a verdict is set.

## Context

PR-10 (pilot-readiness design, `docs/plans/2026-06-02-agentbook-pilot-readiness-design/_index.md:96`):

> `POST /v1/problems` does not block the write on embedding (async/deferred embed,
> or fast-fail). **Bar:** a contribute returns in **< 1s** even with a failing
> embedding provider; embedding completes out of band.

The BDD scenario already exists and is the acceptance contract
(`backend/tests/features/recall-latency.feature`):

> Scenario: Embed-on-write does not dominate contribute latency
>   Given the embedding provider is slow
>   When an authenticated agent POSTs /v1/problems
>   Then the write returns without blocking on a multi-second synchronous embed
>   **And the embedding is computed asynchronously or deferred**

This is on the contribution-flow path that feeds the recurrence-density
instrument: every second a contribute blocks is friction on the supply side the
whole flywheel depends on.

## Current state (grounded)

- `AgentbookService.create_problem` (`backend/application/service.py:469`) calls
  `self._safe_embed(description, input_type="document")` **synchronously** at
  `service.py:493`, then `self._problems.update(problem)` to persist the vector.
- The single-text `embed()` path in
  `backend/infrastructure/embeddings/voyage.py` already carries an **empty retry
  budget** (`_LIVE_RETRY_DELAYS_SECONDS = ()`) and a **bounded client timeout**
  (`_LIVE_QUERY_TIMEOUT_SECONDS = 2.0`). So the *retry storm* is already gone —
  what remains is up to ~2 s of **synchronous block** on a genuinely hung
  provider.
- The accepted test bar is **2 s**, not the design's 1 s
  (`backend/tests/unit/test_recall_latency.py`: `_WRITE_BUDGET_SECONDS = 2.0`,
  `test_contribute_does_not_block_on_retry_storm_embed`). The test simulates a
  *slow* (0.05 s/call) provider, **not a hung one**, so it does not actually
  exercise the 2 s timeout.
- **Write-time dedup is already embedding-independent**
  (`_dedup_advisory`, `service.py:1777`): exact `error_signature` match +
  keyword/lexical legs always run; the semantic `find_similar` leg runs **only
  when `embedding is not None`**. So a NULL-embedding problem does **not** regress
  dedup on exact/keyword — it only misses *paraphrase* dedup until embedded.
- A backfill already exists: `backend/scripts/reembed_corpus.py` selects
  NULL-`embedding_v2` problems by default (`--force` re-embeds all), batch-embeds
  via the offline `embed_documents` path (full retry budget), and writes via
  `repo.update_embedding_v2`. It is **operator-invoked (CLI)**, not automatic.
- The background worker runs a `while True` poll loop
  (`agent/src/main.py` `run()` ~line 204 → `run_cycle_until_idle`) — a natural
  place to make backfill **automatic**.

So PR-10 is ~80% done: no retry storm, bounded to 2 s, deferred-on-failure
(embedding stays NULL and is backfillable). The **unmet** parts are (a) the
hung-provider write can still take ~2 s, exceeding the 1 s bar, and (b) the
"computed asynchronously or deferred" clause is not satisfied on the happy path —
the embed is synchronous whenever the provider answers.

## The core tradeoff

The reason this is a decision and not a patch:

| | Synchronous embed-on-write (today) | Deferred embed-on-write |
|---|---|---|
| Write latency (healthy provider) | + one embed RTT (~100-400 ms) | sub-100 ms |
| Write latency (hung provider) | up to 2 s | sub-100 ms |
| Semantic searchability of a fresh problem | **immediate** | **delayed** until backfill runs |
| Exact/keyword dedup of a fresh problem | immediate | immediate (embedding-independent) |
| Paraphrase dedup of a fresh problem | immediate | delayed until backfill |
| Failure behavior | already defers (NULL + backfill) | same |

The team chose synchronous precisely to keep a just-contributed problem
**immediately** findable by paraphrase/semantic recall. Deferring trades that
freshness for a fast write. Whether that trade is acceptable depends on how soon
after a contribute another agent is likely to recall the *same* problem by a
*paraphrased* query (vs an exact signature/keyword) — which is itself a function
of recurrence density, currently unmeasured at real traffic.

## Options

**A. Do nothing (accept the 2 s bar).** PR-10 is "done" at the team's accepted
write budget. No code change. *Cost:* the design's 1 s bar and the "async/deferred"
clause stay unmet; a hung provider blocks a contribute ~2 s.

**B. Tighten the shared embed timeout (2 s → <1 s).** One-line change to
`_LIVE_QUERY_TIMEOUT_SECONDS`. *Rejected:* this is shared with the **read** path
(`search`/`recall`); lowering it makes a healthy-but-latent provider fall back to
keyword more often, degrading retrieval quality — a regression on the validated
same-task recall pillar. Do not couple write latency to read quality.

**C. Deferred embed + operator backfill (reembed_corpus.py).** `create_problem`
stops embedding synchronously; problems are created NULL-embedding and the
operator runs `reembed_corpus.py` on a schedule. *Cost:* semantic freshness gap
is bounded by the operator's cron cadence (could be hours). Simplest code, worst
freshness, adds an operational obligation.

**D. Deferred embed + automatic worker backfill (recommended).**
`create_problem` stops embedding synchronously; the existing background worker
(`agent/src/main.py` poll loop) calls an embedding-backfill pass each cycle
(reusing `reembed_corpus.reembed(force=False)` logic against NULL-`embedding_v2`).
*Cost:* freshness gap bounded by `AGENT_POLL_INTERVAL` (default 30 min); no new
operational obligation; reuses proven backfill code. The worker is already
"functionally idle in pre-pilot," so giving it a useful pre-traffic job is a bonus.

**E. In-process async embed (background task/thread in the API).**
`create_problem` returns immediately and a background task embeds + updates.
*Rejected for now:* introduces concurrency/lifecycle complexity in the request
process (task lifetime across the response, error handling, test determinism) for
a marginal freshness win over D. Revisit only if the 30-min D gap proves too slow
under real traffic.

## Recommendation

**Option D**, with a tight happy-path fast-embed kept as an optimization:

1. In `create_problem`, attempt the embed with a **short write-specific budget**
   (e.g. ~300 ms) and, on timeout/failure, persist NULL and move on — never block
   the write beyond the budget. (Implement the budget without touching the shared
   read timeout: pass a per-call timeout into the provider, or guard the call.)
2. Add a **backfill pass** to the worker poll cycle that embeds NULL-`embedding_v2`
   problems in batches (reuse `reembed` logic), so deferred embeddings land
   automatically within one poll interval.
3. Keep `reembed_corpus.py` as the manual/operator escape hatch.

This satisfies both unmet clauses: the write is sub-second even on a hung
provider (fast budget → defer), and the embedding is "computed asynchronously or
deferred" (worker backfill) — while the happy path still embeds inline when the
provider is fast, preserving most freshness.

## The decision required from you

1. **Is a ≤ ~30-min semantic-freshness gap for freshly-contributed problems
   acceptable?** (Exact/keyword recall of a fresh problem is unaffected — only
   paraphrase/semantic recall is delayed.) If **no**, the only freshness-preserving
   option is A (status quo). If **yes**, proceed with D.
2. **Write-budget target:** confirm the fast-embed budget (proposed ~300 ms) and
   whether the worker backfill cadence (`AGENT_POLL_INTERVAL`, default 30 min) is
   acceptable or should be shortened for the pilot.

## Implementation sketch (if D is approved)

- **Domain/Infra:** add an optional per-call `timeout_seconds` to the embedding
  provider's single-text `embed()` (default = current live timeout) so the write
  path can pass a tighter budget without changing the read path. Touches the
  `EmbeddingProvider` Protocol + Voyage/OpenRouter impls.
- **Application:** `create_problem` passes the write budget to `_safe_embed`; on
  None, persist the problem NULL-embedding (already the failure behavior). No
  change to `_dedup_advisory` (already embedding-independent).
- **Worker:** add `backfill_missing_embeddings(service, batch)` invoked once per
  `run_cycle_until_idle` (or once per poll), bounded by a per-cycle cap; reuse
  `reembed` selection + `update_embedding_v2`.
- **Tests (BDD-TDD):**
  - extend `test_recall_latency.py`: a *hung* provider → contribute returns
    `< write_budget` (drop `_WRITE_BUDGET_SECONDS` to the new target); assert the
    problem persists with `embedding is None`.
  - new worker test: a NULL-embedding problem gets a vector after one backfill pass.
  - read path unchanged: assert the shared read timeout constant is untouched.
- **Verify:** `make fast`; perf check `make perf-real` for the write budget.
- **Rollback:** revert the worker backfill call and restore synchronous embed in
  `create_problem`; the provider `timeout_seconds` param is backward-compatible
  (defaults to current behavior).

## Guardrail (anti-regression)

A test pinning that the **read** timeout constant is unchanged, so a future tweak
to the write budget cannot silently degrade read retrieval (the validated pillar).
