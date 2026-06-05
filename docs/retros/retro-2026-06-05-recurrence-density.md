# Retrospective — 2026-06-05 (recurrence-density + vision-roadmap window)

**Scope:** plans completed since the last `retrospective_run` (2026-06-02T07:51). Three folders, 10 evaluation reports:
- `2026-06-02-agentbook-pilot-readiness-design` — `evaluation-design-round-1.md` (REWORK), `evaluation-design-round-2.md` (PASS)
- `2026-06-02-agentbook-pilot-readiness-plan` — 6 code-batch reports (all PASS)
- `2026-06-04-agentbook-vision-roadmap-design` — round-1 (PASS)
- `2026-06-04-recurrence-density-instrument-plan` — 4 code-batch reports (all PASS)

Checklists analyzed: `design-v2`, `plan-v2`, `code-v2`. Git depth 498 commits.

**Headline:** 9 of 10 reports are all-PASS, zero rework. The single checklist FAIL (`DESIGN-BDD-01`, pilot-readiness design round 1) was caught correctly and forced a clean one-round rework. This is an overwhelmingly green window; the calibrated outcome is **0 checklist changes applied** — all forward candidates rest on a single plan and are deferred with evidence.

## Pre-Checks

- **A (INSUFFICIENT-POST-PLAN):** N/A — most recent `plan_completed` is the pilot-readiness plan (~72h ago, not <24h). The recurrence-density plan is not yet in `plans-completed.jsonl` (the Stop hook keys off `handoff-summary-*` files; this run used a single rewritten `handoff-state.md`), so its post-plan-diff has no signal (and it just committed — zero corrections regardless).
- **B (memory priors):** `feedback_heavy_web_search_in_adversarial_loops` (working-style prior → Phase 5b note, not a grep-able checklist item); anti-monotonic-growth stance reinforced by the prior run's `CODE-SCOPE-02` removal. No memory prior contradicts a proposal.
- **Phase 0:** all three modes have v1/v2 — seed skipped.

## Phase 2 — Analysis

### Table 1 — Failure frequency

| Item ID | Checklist | Distinct plans FAILed | Evidence |
|---|---|---|---|
| `DESIGN-BDD-01` | design-v2 | 1 (pilot-readiness-design) | round-1: two requirement legs (PR-3 cross-transport rejection parity; PR-18 length-floor error states threshold) had no Gherkin scenario → REWORK; fixed round-2 → PASS |

The only FAIL in the window. Load-bearing item working as designed; no item failed in ≥2 plans.

### Table 2 — Plateau / REWORK

The pilot-readiness design round-1→2 was **caught by `DESIGN-BDD-01`** (the check fired and forced the fix — no coverage gap). No 2-consecutive-round plateau. One latent issue surfaced post-PASS by human review: a PR-2/PR-8 vocabulary contradiction (`problem_id` named a *valid* `trace` alias in one scenario but used as the *unknown-arg* example in another). `DESIGN-CONSISTENCY-01` covers numeric-only; `DESIGN-CONSISTENCY-02` policy-location-only → **non-numeric alias-consistency GAP**, but weak evidence (1 plan, post-PASS, self-corrected, no rework).

### Table 3 — Never-failing items (REMOVE scan)

**No clean REMOVE candidate.** Every 0-fail item across design-v2 (3 reports) and code-v2 (10 reports) is either a routinely-firing gate (`CODE-LINT-01`, `CODE-VERIFY-01`, `CODE-EDIT-02`, `CODE-SCOPE-01`, `CODE-TEST-03`, `DESIGN-BDD-01`) or an explicit regression/safety guard kept despite 0 fails (`CODE-TEST-01/02`, `CODE-MIGRATION-01/02`, `CODE-VERIFY-02`, `CODE-ASSUME-01/02`, `DESIGN-BDD-03/04`, `DESIGN-REFERENCE-01`, `DESIGN-SPECIFICITY-02`). `CODE-A11Y-01` is N/A across all 10 backend batches but would fire on a frontend plan — not a by-design never-fires target. The anti-growth scan ran and honestly found nothing removable this window.

### Table 4 — Variety gaps

Two cross-cutting breaks in recurrence-density batch 4, both **caught by the full-suite gate (`make fast` / `CODE-VERIFY-01`)** and remediated under `CODE-SCOPE-01` exc (b):
1. Dashboard `problem_id` returned as `UUID` vs the `str` contract — passed the per-pair coordinator's narrower check, surfaced only at batch aggregation.
2. Two pre-existing MCP signature-assertion tests broke when `caller=` was added — not caught until the full suite ran.

Genuinely uncovered: (a) no item proactively flags "a new kwarg/signature change will break existing tests pinning the old signature — grep callers/assertions first" (inverse of `CODE-ASSUME-01/02`); (b) no item says "per-pair green is insufficient — run the full suite across the combined change before declaring a pair done." Both manifested in **exactly one plan / one batch**.

## Phase 3/4 — Proposals: 0 applied, 3 deferred

All forward candidates are single-plan, below the 2-plan ADD / standard thresholds. Adding them now would over-fit one batch and violate the anti-monotonic-growth discipline. **Deferred with recorded evidence** — a future retro promotes any that recur:

| # | Type | Target | Evidence status | Rationale |
|---|---|---|---|---|
| D1 | ADD | code-v2 `CODE-ASSUME-03` (signature-break guard) | 1 plan (recurrence batch 4, MCP `caller=`) — below 2-plan bar | "Before adding a kwarg/changing a signature, grep existing tests/callers pinning the old signature and update them in the same change." Real, generalizable; monitor for a 2nd occurrence. |
| D2 | MODIFY | code-v2 `CODE-VERIFY-01` (full-suite per-pair) | 1 plan; item already *caught* the bug at aggregation | Make explicit that per-pair coordinators run the full suite across the combined change before declaring done. Borderline — partly an orchestration concern (see Phase 5b), not purely checklist wording. |
| D3 | ADD | design-v2 alias/vocabulary consistency | 1 plan, post-PASS, self-corrected | "An identifier presented as a valid alias in one scenario must not be the unknown/invalid example in another." Weakest; monitor only. |

**REMOVE:** none. **PROMOTE:** none. **Self-rejected:** none (the three are deferred-for-insufficient-evidence, not contradictions of history/memory). **plan-v2:** uncalibratable — zero plan-mode evaluation reports in this window.

No checklist version incremented (no proposal applied). `design-v2`/`plan-v2`/`code-v2` remain current.

## Phase 5 — Harness Health (advisory)

- **5a (post-plan correction mining):** no signal — the in-scope completed plan (pilot-readiness) has been stable since 2026-06-02 with `total==0` post-plan corrections; the recurrence-density plan's fixes happened *within* execution (caught by the `make fast` gate before the final commit), not as post-plan corrections. The harness's full-suite gate did its job — no shipped evaluator blind spot to mine.
- **5b (process/working-style notes, not checklist changes):**
  - **Concurrent-coordinator orchestration:** splitting a batch into parallel coordinators and telling each to skip `make fast` (to avoid clobbering during concurrent edits) means cross-cutting breakage only surfaces when the main agent runs the combined suite after merge. This worked here (both batch-4 breaks were caught and fixed before commit) but cost extra round-trips. Orchestration rule for next time: when fanning a batch into concurrent coordinators, the main agent MUST run the full suite post-merge before declaring the batch done — which is the D2 candidate, better lived as an orchestration habit than a checklist item until a 2nd occurrence justifies the item.
  - **Web-search feedback** ([[feedback_heavy_web_search_in_adversarial_loops]]): the user asked for heavy, continuous web search in generate/adversarial-evaluate loops. This is a working-style change for *research/design/evaluation generation*, not a checklist-evolution input — importing an "evaluators must web-search" item would be the external-pattern import the retro protocol explicitly cautions against. Logged as a forward note; applies to the roadmap's upcoming cross-task experiment design and bootstrap domain selection.

## Summary

**0 proposals approved, 0 rejected, 3 deferred (single-plan evidence). No checklist version change.** A clean, green window — the correct retrospective outcome is restraint, not invention. The strongest forward signal (D1, signature-break guard) is recorded for promotion if it recurs.
