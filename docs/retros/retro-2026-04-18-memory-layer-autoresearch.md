# Retrospective — Memory Layer + Autoresearch Alignment (2026-04-18)

## Context

First plan in this repository. 42 tasks delivered across backend (Python + Alembic), frontend (Next.js), and agent service. Three skills ran in sequence:

1. `superpowers:brainstorming` → `docs/plans/2026-04-18-memory-layer-autoresearch-design/` (committed 6cd712d)
2. `superpowers:writing-plans` → `docs/plans/2026-04-18-memory-layer-autoresearch-plan/` (committed 29b71c9 and later)
3. `superpowers:executing-plans` → implementation landed across 5 commits (2d072ff, fb8ee9f, 20251f3, migrations, frontend)

**Data constraints**: Only one plan exists, so ADD/REMOVE/MODIFY/PROMOTE proposals per the skill's evolution thresholds are deferred. The executing-plans phase ran linear (not per-batch evaluator mode), so no `evaluation-round-*.md` artifacts were produced. This retro is observational — it seeds v1 checklists distilled from the patterns that actually surfaced during execution.

## Analysis

### Failure frequency

Not applicable — no per-batch evaluations ran. The brainstorming evaluator emitted one REWORK (two items: BDD coverage gap for sandbox DoS gates, BDD coverage gap for backfill rollback) which the main agent resolved in-skill. The writing-plans evaluator emitted one REWORK (cosmetic: missing `**depends-on**` header on task 001). Both were resolved on re-evaluation.

### Plateau tasks

None in the formal 2+ REWORK sense. Mid-implementation friction points that would have surfaced as plateaus under a tighter evaluator:

| Friction | Recurrence | Root cause |
|---|---|---|
| Assumed test-fixture names not in conftest | 3× | Agent guessed `in_memory_service`, `list_all_active`, `_calls` without grepping |
| Write → Edit stale-file cycle | ~5× | Biome formatter edited files post-Write; subsequent Edit old_string became stale |
| Biome auto-removed unused import | 1× | `health_router` import dropped by formatter until re-added adjacent to siblings |
| a11y rule: `aria-label` on `<span>` without `role` | 1× | Biome rejected; fixed by adding `role="img"` |
| TypeScript type-name drift | 2× | Imported `Problem` instead of `ProblemListItem`; used `has_verified_outcomes` field that isn't on the type |

### Never-failing items

N/A — insufficient reports per item.

### Variety gaps

One notable gap even in a single run: no harness caught the agent's tendency to invent fixture/method names before verifying against conftest or the target module. A `code-v1` item targeting "grep before naming" would have caught all three friction cases above.

## Proposals

**0 formal proposals** (minimum-data thresholds not met).

Instead, seed initial `design-v1.md`, `plan-v1.md`, `code-v1.md` checklists with items distilled from this plan's actual patterns. These become the v1 against which future plans are evaluated. See `docs/retros/checklists/*-v1.md` written alongside this retro.

Seeding rationale (not per-item evidence):

- **design-v1**: items derived from the brainstorming REWORK signals — BDD coverage completeness and cross-file numeric consistency.
- **plan-v1**: items derived from the writing-plans evaluator feedback — task-file structural uniformity, BDD mapping density, Red-before-Green ordering.
- **code-v1**: items derived from the execution-phase friction log above — verify-before-naming, Read-after-reformatter, a11y role requirements, test-double isolation at boundaries.

## Harness Health

- **Brainstorming (design mode)**: PASS. Evaluator caught two concrete BDD coverage gaps and one style-consistency issue. Keep the evaluator at standard intensity for next plan.
- **Writing-plans (plan mode)**: PASS. Evaluator caught one cosmetic issue and confirmed 42/42 BDD scenario coverage + zero dependency cycles + all Red-before-Green pairs correct. Keep at standard intensity.
- **Executing-plans (code mode)**: NOT EXERCISED. The per-batch evaluator was not spawned because linear execution was chosen for speed. Recommendation: next plan should enable evaluator mode at `standard` intensity so code-mode checklist items start accumulating reports. Until 10+ reports per item exist, REMOVE proposals stay blocked.
- **Intra-plan learning**: no data (no multi-batch evaluation occurred). Re-assess after next plan.

## Pre-Edit Snapshot

No prior checklists exist; this run creates v1 files rather than v{N+1}. Rollback = delete the newly created `docs/retros/checklists/*-v1.md` files.

## Summary

- Plans analysed: 1 (`2026-04-18-memory-layer-autoresearch-plan`)
- Evaluation reports read: 0 (none persisted to plan directory)
- Formal proposals: 0 approved / 0 rejected / 0 deferred-for-data
- Checklists created: `design-v1.md`, `plan-v1.md`, `code-v1.md`
- Harness recommendation: enable per-batch evaluator at `standard` intensity during next `executing-plans` run to begin generating code-mode report history
