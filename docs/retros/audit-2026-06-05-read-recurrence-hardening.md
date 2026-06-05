# Audit — read / recurrence / synthesis hardening (2026-06-05)

A correctness audit of the core read, recurrence-density, and synthesis paths,
triggered by the vision-completion question ("is the shared-memory vision
achieved?"). The verdict on the vision is unchanged — **partially achieved,
~30%**, gated on real external traffic (see `docs/vision-reflection-2026-06-04.md`).
This pass did the highest-leverage thing engineering can do *before* traffic:
make the metric that gates the vision (recurrence density) trustworthy, and stop
unvalidated content from leaking into trusted read surfaces.

All findings were RED-proven, fixed BDD-TDD, and committed on
`feat/recurrence-density-instrument` (full suite 819 passed; integration-verified
end-to-end against a live in-memory server).

## Bugs fixed (7)

| # | Path | Bug | Fix |
|---|---|---|---|
| 1 | `presentation/api/routes/search.py` | REST `/v1/search` did not thread caller identity into the recurrence recorder (MCP recall did) | build a `CallerContext` from the agent / remote-addr hash; shared `core/ip_hash.py` |
| 2 | `application/service.py` `search_problems` | the result cache returned **before** `_record_query_event`, so distinct agents issuing the same query within the cache window were never recorded | record on the cache-hit path too |
| 3 | `application/_recurrence.py` | `organic_recurrence` excluded by the **querier's** seed status (already filtered as `is_seed_replay`) — dead code; the matched **contributor's** seed status was never captured | add `QueryEvent.is_seeded_hit` (stamped at record time via `_is_seeded_hit`), key organic off it; SQLAlchemy column + migration `u6v7w8x9y0z1` |
| 4 | `application/service.py` `_search_problems` | zero-solution rows were demoted to the no-solution tier **after** sort/truncation, so a hollow exact hit could seize the only slot at small `limit` and force `no_good_match` | stamp `has_help` + demote **before** the sort |
| 5 | `application/service.py` `_pick_best_solution` | the search reliance target filtered only on `review_status`, surfacing unpromoted **candidates** / demoted proposals that every other surface hides | use the canonical `_is_visible_solution` |
| 6 | `application/service.py` `get_cross_problem_solutions` | same candidate leak in cross-problem surfacing | use `_is_visible_solution` |
| 7 | `application/service.py` `synthesize_solutions` | the `active` set (non-superseded) counted pending candidates toward the `≥2` gate and merged their unvalidated content into the canonical solution (then froze them superseded) | require `_is_visible_solution` too; doc updated (`docs/mcp-setup.md`) |

Bugs 1–3 made the recurrence instrument under-count real traffic / inflate the
organic (network-effect) signal — directly distorting the variable that gates a
seeded-domain pilot and the multiplayer decision. Bugs 4–7 are one theme: the
canonical `_is_visible_solution` filter ("approved AND not candidate/demoted")
was not applied uniformly, so unvalidated content leaked into search, cross-task
surfacing, and the canonical synthesis.

Also shipped: PR-16 (self-describing structured-knowledge write fields, mirroring
MCP) and the PR-10 deferred-embed design (`docs/plans/2026-06-05-pr10-deferred-embed-design.md`).

## Verified clean (audited, no change needed)

- reliance-target resolver consistency (search `_pick_best_solution` vs GET/trace
  `_resolve_book_solution`, now aligned after #5)
- recurrence dedup window (`add_with_dedup`) — conservative-by-design
- effective-reporter counting + anti-Sybil clustering (`detect_clusters`,
  `_pair_signals`) — singletons counted, no missing outcome-signal dependency
- candidate promotion/demotion + `solution_count` bookkeeping — no double-count
- `outcome_summary` aggregation (covers all visible solutions — PR-15)
- `_recompute_outcome_counters` — derived from ground truth
- `get_problem_timeline` / `get_solution_lineage` — history/provenance views
  correctly include all solutions, with cycle protection and chronological order

## Design notes (intentional, not bugs)

- **`problem.best_confidence` is a monotonic high-water-mark** (explicit at
  `service.py:534`). Load-bearing for the research worker's prioritization
  (`best_confidence < threshold → research`) and `previous_best_confidence`
  delta tracking. It can therefore exceed the current visible reliance target's
  confidence; this is by design, not a leak. (The per-solution
  `best_solution.confidence` *is* visible-only after fix #5.)

## Bottom line

Seven real correctness bugs removed from the decisive path; the recurrence
instrument and the reliance-target contract are now trustworthy for when traffic
arrives. None of this is traffic — the remaining ~70% of the vision (real
external recall/contribution, confidence from real outcomes, worker hill-climbing
on a real gradient) is a market outcome, not an engineering deliverable. The
pre-traffic engineering frontier for the read/recurrence/synthesis core is
reached.
