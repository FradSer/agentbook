# Live Research Banner — Design Evaluation Report (Round 1)

Evaluator: `superpowers:superpowers-evaluator` (design mode).
Checklist: `docs/retros/checklists/design-v1.md`.
Date: 2026-05-01.

## Checklist Results

| Item ID | Check | Result | Evidence |
|---|---|---|---|
| DESIGN-STRUCTURE-01 | `_index.md` section heading order: Context, Discovery Results, Requirements, Rationale, Detailed Design, Design Documents | PASS | `_index.md` headings appear in exact required order |
| DESIGN-STRUCTURE-02 | Folder name ends in `-design` and starts with ISO date | PASS | Folder name `2026-05-01-live-research-banner-design` matches `YYYY-MM-DD-<topic>-design` |
| DESIGN-STRUCTURE-03 | Complex design has all four files | PASS | `_index.md`, `bdd-specs.md`, `architecture.md`, `best-practices.md` all present |
| DESIGN-BDD-01 | Every Requirement maps to ≥1 Gherkin scenario | PASS | F1 reuses-tokens scenario plus implicit render scenarios; F2 (multi-problem); F3 (transition without flash); F4 (cold start + idle copy); F5 (initial REST snapshot); F6 (drop + REST fallback); F7 (stale row, agent crash protection); F8 (`list_being_researched`, `get_latest_cycle_at`); NF1 (a11y aria-live, focusRing, reduced-motion); NF2 (10-s cache); NF3 (concurrency cap, REST limit); NF4–NF6 are non-behavioral build constraints (no scenario expected) |
| DESIGN-BDD-02 | Error paths covered, not just happy path | PASS | Error/edge scenarios for SSE drop + REST fallback, fresh-snapshot reconnect, agent crash protection, stale row falling out of active set, concurrency 429, REST 429, 15-min hard close, empty `research_cycles` |
| DESIGN-BDD-03 | DoS / resilience / rate-limit gates have scenarios | PASS | Per-IP concurrency cap, REST `dynamic_search_limit`, heartbeat keeps proxies open, 15-min hard timeout, 10-s `last_cycle_at` cache — each gate from `best-practices.md` §B1/§B2 has a matching scenario |
| DESIGN-BDD-04 | Zero-downtime migration scenarios | PASS (borderline) | The only schema change is `CREATE INDEX CONCURRENTLY ix_problems_research_started_at … WHERE research_started_at IS NOT NULL`. `CONCURRENTLY` is inherently zero-downtime and idempotent on retry; the change is purely additive (no column drop, no data backfill, no read-path coupling). No mid-run-failure scenario exists, but the migration shape does not create a state machine to break |
| DESIGN-CONSISTENCY-01 | Numeric values identical across files | PASS | 360 s freshness, 2 s poll, 10 s cache, 25 s heartbeat, 15-min hard timeout, 5/20/200 concurrency caps, 30/300 per-min REST limits, 300-char description cap, 60 s reopen probe, 10 s REST fallback interval, 3-error threshold — all four files cite the same numbers |
| DESIGN-CONSISTENCY-02 | Policy-location claims enforced by BDD | PASS | "Freshness lives in `_is_being_researched`" enforced by stale-row scenarios; "no `Last-Event-ID` replay; server re-emits fresh `snapshot`" enforced by reconnect scenario; "heartbeat is a comment line, not `data:`" enforced by heartbeat scenario; "10 s in-process cache for `last_cycle_at`" enforced by cache scenario; "no new CSS tokens" enforced by reuses-tokens scenario |
| DESIGN-SCOPE-01 | Every requirement traces to user-confirmed scope | PASS | User scope item 1 (Hill-climb 360 s) → F7; item 2 (hero-bottom inline banner) → F1 plus explicit Out of Scope #2/#3 excluding `/memories` tab and global sticky overlay; item 3 (SSE chosen over 30 s polling) → F5/F6 plus Rationale "Why SSE and not 30 s polling"; item 4 (idle copy) → F4 |
| DESIGN-SCOPE-02 | Rationale justifies each numeric threshold | PASS (borderline) | Justified: 360 s, 2 s poll, 10 s cache, 25 s heartbeat, 15-min hard timeout, 5/20/200 concurrency caps, 300-char cap, 30/300 REST limits. Borderline: 60 s reopen-probe interval, 3 consecutive errors threshold, 1 s a11y debounce — reasonable defaults, not explicitly justified |
| DESIGN-REFERENCE-01 | External references older than 14 days carry re-verification task | PASS | Discovery Results and architecture §0 cite only internal repository file:line references (verified 2026-05-01 per `architecture.md` header); no external web docs are load-bearing for architectural decisions |
| DESIGN-SPECIFICITY-01 | Interface changes specify exact file paths and function signatures | PASS | `list_being_researched(timeout_seconds: int = 360) -> list[Problem]`, `get_latest_cycle_at() -> datetime \| None`, `get_live_research_snapshot() -> dict` with full return shape and worked example, `fetchLiveResearchSnapshot(): Promise<LiveResearchSnapshot>`; file plan tables in §2 give exact paths for every changed/created file |
| DESIGN-SPECIFICITY-02 | Migration plans include exact SQL or Alembic op names | PASS | `architecture.md` provides exact SQL `CREATE INDEX CONCURRENTLY ix_problems_research_started_at ON problems (research_started_at) WHERE research_started_at IS NOT NULL;` and exact Alembic file path pattern |

## Rework Items

(none — verdict is PASS)

## Recommendations (non-blocking)

1. **DESIGN-BDD-04 borderline.** `architecture.md` could add one sentence
   to §2 or to the migration risk register noting that `CREATE INDEX
   CONCURRENTLY` leaves an `INVALID` index on interruption and the
   rollback procedure is `DROP INDEX IF EXISTS
   ix_problems_research_started_at;` before re-running. No code or
   schema change required; one line in the migration's docstring
   template.

2. **DESIGN-SCOPE-02 borderline.** Three UX/reliability constants are
   not explicitly justified: (a) 60 s re-open probe while in REST
   fallback mode, (b) 3 consecutive `onerror` events before fallback,
   (c) 1 s a11y announcement debounce. A one-line note per constant in
   the Rationale section would close the loop. None are load-bearing
   for correctness.

3. **F1 banner placement** has no direct behavioural BDD scenario — the
   closest is "Banner reuses existing CSS tokens", which asserts class
   names but not document position. A one-line scenario could assert
   the banner mounts after the hero subtitle and before the Tabs
   region.

4. **Out-of-scope #1 explicitly preserves the existing per-card
   Researching badge.** No BDD scenario asserts the per-card badge
   still works after the banner is added. A smoke scenario "Per-card
   Researching badge continues to render alongside the banner" would
   lock the regression boundary.

5. **Promotion path documented but not test-anchored.** `architecture.md §1`
   says "if connections per worker exceed ~200 or research toggles
   exceed ~10 Hz, extract to centralised poller". The 200 cap is
   enforced in code, but the 10 Hz toggle threshold has no observable
   assertion. This is operational guidance, not a current requirement.

## Verdict

**PASS** — all 14 checklist items resolve to PASS (two with borderline
notes that do not affect the binary result). No rework required. The
design is committed-ready.

The borderline notes (DESIGN-BDD-04 on migration rollback procedure,
DESIGN-SCOPE-02 on three UX-tuning constants) are recorded for
visibility into checklist evolution but do not block the design.

## Post-Verdict Resolution (2026-05-01)

Per user request, all 5 non-blocking recommendations were applied
before commit:

1. **DESIGN-BDD-04 borderline → resolved.** `architecture.md §2` migration row now carries an explicit rollback note: `CREATE INDEX CONCURRENTLY` leaves an `INVALID` index on interruption; rollback procedure is `DROP INDEX IF EXISTS ix_problems_research_started_at;` before re-running. Also documented in the migration's docstring per the file plan.
2. **DESIGN-SCOPE-02 borderline → resolved.** `_index.md` Rationale section gained a new "UX-tuning constants" subsection justifying (a) 60 s re-open probe, (b) 3 consecutive `onerror` threshold, (c) 1 s `aria-live` debounce.
3. **F1 banner placement → resolved.** `bdd-specs.md` adds `@frontend @smoke` scenario "Banner mounts between hero subtitle and Tabs in document order" asserting position relative to the hero subtitle and the Tabs `role="tablist"` region.
4. **Per-card badge regression boundary → resolved.** `bdd-specs.md` adds `@frontend @smoke` scenario "Per-card Researching badge continues to render alongside the banner" asserting the existing `ProblemCard` badge and `.research-active` class survive the banner addition.
5. **Promotion-path 10 Hz threshold → resolved.** `bdd-specs.md` adds `@backend` scenario "Toggle-rate metric exposes the centralised-poller promotion threshold" requiring the SSE handler to log structured `research_started`/`research_ended` events from which operators can compute toggles-per-second, with 10 Hz documented as the promotion signal (no production alert below that threshold).

Verdict remains **PASS**; no re-run of the evaluator is required because
all changes are additive and traceable.

