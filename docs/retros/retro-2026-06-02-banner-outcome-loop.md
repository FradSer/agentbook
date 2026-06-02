# Retrospective: Live Research Banner + Outcome-Feedback Loop (2026-06-02)

**Date**: 2026-06-02
**Plans analyzed**: `2026-05-01-live-research-banner` (design + plan + 7 code batches), `2026-05-27-agentbook-outcome-loop` (design + plan + 4 code batches)
**Reports read**: 16 evaluation reports (3 design, 2 plan, 11 code-batch)

## Pre-Checks

- **Pre-Check A (INSUFFICIENT-POST-PLAN)**: `docs/retros/plans-completed.jsonl` is absent → no `completion_commit` for any plan → skipped silently. Phase 1 step 6 / Phase 5a post-plan-diff mining is therefore unavailable this run (no 1-plan ADD override).
- **Pre-Check B (calibration priors)**: scanned the injected `MEMORY.md` index. Relevant priors: a harness-design **simplify / anti-growth** stance and a **skills-are-user-invoked-only** stance ([[feedback_skills_user_only]]). No memory records a prior checklist-item rejection. These priors *favor* this run's direction (1 REMOVE + 2 clarifying/tightening MODIFYs, zero net new items) and contradict none of the proposals — no self-rejection triggered. The evolution-log holds only the three v1 `seed` events (no prior `item_*` decisions to calibrate against), so the log and memory agree: nothing to suppress.
- **Phase 0**: `code-v1.md`, `design-v1.md`, `plan-v1.md` all present → seeding skipped. (This run is the first true *evolution* run; the 2026-04-18 retro only seeded v1.)
- **Scope note**: `evolution-log.jsonl` contains no `retrospective_run` marker, so auto-scope falls back to all plans with evaluation reports completed since the v1 seed — the two plans above.

## Failure Frequency

Distinct plans where each checklist item FAILed (hard FAIL only; borderline-PASS excluded):

| Mode | Item ID | # plans FAILed | Where |
|---|---|---|---|
| design | DESIGN-BDD-01 | 1 | outcome-loop r1 (R7 / R6 uncovered) — fixed r2 |
| design | DESIGN-CONSISTENCY-01 | 1 plan / **2 rounds** | outcome-loop r1 (26 vs 32 count) → r2 (residual stale breakdown `_index.md:115`) |
| design | DESIGN-SCOPE-02 | 1 | outcome-loop r1 (`min_failure_count=3`, `max_turns_per_run=4` unjustified) — fixed r2 |
| plan | — | 0 | both live-research plan rounds PASS 19/19 |
| code | — | 0 hard FAIL | all 11 batches PASS; outcome-loop batch 4 task 013 was PASS-WITH-ACCEPTANCE-GAPS (see Variety Gaps) |

DESIGN-BDD-01 and DESIGN-SCOPE-02 each FAILed in a single plan, single round, and were cleanly fixed in one pass — the items fired correctly; that is the checklist working, not a coverage gap. No proposal warranted.

## Plateau Tasks

| Item | Recurrence | Root cause | Action |
|---|---|---|---|
| **DESIGN-CONSISTENCY-01** (outcome-loop) | REWORK r1 → REWORK r2 (2 consecutive rounds) | The scenario count was restated in multiple places *within the same file*; the r1 fix updated the headline (`_index.md:105/109`) but missed a duplicate parenthetical breakdown (`_index.md:115` still read `(refinement: 10, parser: 9, rotation: 7)`, summing to the stale 26). r2 report: "Sweep missed the duplicate." | **MODIFY DESIGN-CONSISTENCY-01** (applied) |

This is the only true plateau (2+ consecutive REWORK rounds) across both plans. It cost a full extra evaluation round. The existing item checked *cross-file* identity but did not prescribe an exhaustive same-value grep that would have caught an intra-file duplicate.

## Never-Failing Items (REMOVE analysis)

| Mode | Item | Reports | PASS | FAIL | N/A | Verdict |
|---|---|---|---|---|---|---|
| code | **CODE-SCOPE-02** ("commit message names feature scope") | 10 | 0 | 0 | **10** | **REMOVE** — structurally inapplicable: per-batch coordinators never commit (commit is the parent agent's job). Zero signal, pure checklist load. |
| code | CODE-MIGRATION-01 / -02 | 10 | 0 | 0 | 9 (1 PARTIAL/NOT-VERIFIED) | KEEP — real check; the one applicable batch (live-research b1) could not reach a live DB from the agent env. Conditional, not dead. |
| design | DESIGN-REFERENCE-01 | 3 | 3 (all trivial: "no external URLs") | 0 | 0 | KEEP — fires conditionally; both plans happened to have no load-bearing external refs. Not monotonic-growth bloat. Re-assess if it stays trivial across more plans (note in Harness Health 5b). |
| code | CODE-LINT-01 / -VERIFY-01 / -VERIFY-02 / -ASSUME-01 / -ASSUME-02 / -EDIT-01 | 10 | ~10 | 0 | few | KEEP — load-bearing gates that actively fired (autoflake/grep-before-naming friction in live-research b4/b5; Red-shape gates in outcome-loop). Zero-FAIL here means "working", not "dead". |

CODE-SCOPE-02 is the clean REMOVE: never PASS, never FAIL, always N/A — the canonical never-firing item the counter-monotonic-growth rule targets. The commit-scope concern is not lost; it lives at commit time (`git:commit` skill), the wrong layer for a per-task code-batch gate.

## Variety Gaps

| Gap | Plan | Detail | Action |
|---|---|---|---|
| Green gate passes while impl acceptance bullets remain unimplemented | outcome-loop batch 4, task 013 | The Red/Green test exercised the extracted primitive (`run_chain`) directly, so 3 impl-side acceptance bullets (`main()` rotate/other split, `_has_memory` `good_rotate` branch, `bootstrap_outcomes_log` archive scan) Green'd without being landed. Caught only by post-hoc coordinator audit (filed BATCH4-013-{A,B,C}); required a full rework round. The batch report itself filed this as a checklist-evolution candidate. | **DEFER ADD** — 1-plan evidence only; below the 2-plan ADD threshold, and no post-plan-diff 1-plan override available this run (no `completion_commit`). Recorded with full evidence for the next retrospective; promote to ADD if a 2nd plan exhibits "test targets primitive, not the integration entry point named in the acceptance bullets". |

## Evolution Proposals

| # | Type | Mode | Item ID | Status |
|---|------|------|---------|--------|
| 1 | MODIFY | design | DESIGN-CONSISTENCY-01 | APPLIED → design-v2.md |
| 2 | MODIFY | plan | PLAN-TASK-04 | APPLIED → plan-v2.md |
| 3 | REMOVE | code | CODE-SCOPE-02 | APPLIED → code-v2.md |
| 4 | ADD | code | (test-targets-entry-point) | DEFERRED (1-plan evidence) |
| 5 | MODIFY | plan | PLAN-CONTRACT-02 | DEFERRED (no rework cost incurred) |

```
Proposal 1: MODIFY design/DESIGN-CONSISTENCY-01
Description: numeric values identical across design files.
Rationale: a 2-consecutive-round plateau cost an extra evaluation round; the
  item checked cross-file identity but not intra-file duplicate restatements,
  so a single-location fix left a stale parenthetical breakdown behind.
Evidence: outcome-loop design r1 (26 vs 32 scenario count) -> r2 residual at
  _index.md:115 ("(refinement: 10, parser: 9, rotation: 7)") -- "Sweep missed
  the duplicate." Tightened to require a grep of the prior value across all
  files with zero residual occurrences, including same-file duplicates.
Outcome: applied

Proposal 2: MODIFY plan/PLAN-TASK-04
Description: task filename convention.
Rationale: the v1 phrasing `task-<NNN>-<feature>-<type>.md` is ambiguous about
  whether `<type>` is a separate filename segment or slug-embedded, producing
  borderline adjudication in BOTH rounds of the live-research plan; round-2
  recommendation #1 explicitly asked to clarify it.
Evidence: live-research plan r1 (PLAN-TASK-04 borderline) and r2 (PLAN-TASK-04
  PASS-borderline + explicit "consider clarifying the checklist item" rec).
  Clarified to a binary rule that accepts both slug-embedded type and
  feature-only foundation slugs; bans borderline on the foundation-slug case.
Outcome: applied

Proposal 3: REMOVE code/CODE-SCOPE-02
Description: a task's commit message names the feature scope, not file moves.
Rationale: N/A in all 10 per-batch code reports because per-batch coordinators
  never commit -- commit is the parent agent's responsibility. Zero signal,
  pure checklist load; the concern belongs to a commit-time gate (git:commit
  skill), not a per-task code-batch checklist.
Evidence: live-research batches 1-7 + outcome-loop batches 2-4 -- every one
  records CODE-SCOPE-02 as "N/A | Parent/coordinator owns commit".
Outcome: applied
```

## Pre-Edit Snapshot

Rollback for any applied edit = delete the new `{mode}-v2.md`; the `{mode}-v1.md` originals are preserved unchanged. Full v1 bodies are committed in `docs/retros/checklists/{code,design,plan}-v1.md` (git history is the snapshot; no inline duplication needed since v1 files are untouched on disk).

- **design-v1.md → design-v2.md**: DESIGN-CONSISTENCY-01 only. Rollback: `rm docs/retros/checklists/design-v2.md`.
- **plan-v1.md → plan-v2.md**: PLAN-TASK-04 only. Rollback: `rm docs/retros/checklists/plan-v2.md`.
- **code-v1.md → code-v2.md**: CODE-SCOPE-02 removed. Rollback: `rm docs/retros/checklists/code-v2.md`.

## Harness Health

### 5a — Post-Plan Correction Mining
Unavailable this run: no `plans-completed.jsonl` / `completion_commit`, so `lib/post-plan-diff.sh` could not classify post-plan commits. The highest-value signal source is dark until executing-plans starts emitting completion records. **Recommendation**: ensure future plan completions log to `docs/retros/plans-completed.jsonl` with `completion_commit` so post-plan correction mining (and the 1-plan ADD override) becomes available.

### 5b — Usage-Driven Recommendations (report notes only)
- **Plan mode all-PASS**: both live-research plan rounds passed 19/19. With only one plan exercising the plan checklist post-seed, this is not yet the "3+ plans all first-round PASS" bar for reducing plan-mode evaluation. Re-assess next run.
- **DESIGN-REFERENCE-01 trivially passing**: 3/3 design reports passed it only because no external references were load-bearing. If it stays trivial across 3+ plans it becomes a REMOVE candidate (3+ reports threshold) — flag, do not act yet.
- **Code-mode evaluator availability**: every batch report notes `superpowers:superpowers-evaluator` is "not registered in this session" — evaluations were inline-coordinator equivalents. Not a checklist issue, but the code-mode reports are self-audits; an external evaluator pass would harden the signal these retrospectives consume.

## Summary

- **Plans analyzed**: 2 (live-research-banner, agentbook-outcome-loop)
- **Reports read**: 16 (3 design, 2 plan, 11 code-batch)
- **Proposals**: 3 approved / 0 rejected / 2 deferred
- **Checklists updated**: `design-v2.md`, `plan-v2.md`, `code-v2.md` (one change each; net new items = 0 — 1 removed, 2 tightened/clarified)
- **Deferred for evidence**: code ADD (test-targets-entry-point, needs 2nd plan); plan MODIFY (PLAN-CONTRACT-02 "Intent only" relaxation, no rework cost yet)
- **Next action**: run retrospective again after 2+ more plan executions; re-evaluate the deferred code ADD and DESIGN-REFERENCE-01. Restore `plans-completed.jsonl` logging to unlock post-plan correction mining.
