# Evaluation: agentbook Outcome-Feedback Loop design (round 1)

**Mode**: design
**Folder**: `/Users/FradSer/Developer/FradSer/agentbook/docs/plans/2026-05-27-agentbook-outcome-loop-design/`
**Checklist**: `/Users/FradSer/Developer/FradSer/agentbook/docs/retros/checklists/design-v1.md`

## Justification pre-check (JUST-01)

Scanned `_index.md` lines 1-100 for `STATUS:.*NOT.JUSTIFIED`, `DESIGN-NOT-YET-JUSTIFIED`, `DESIGN-CONSIDERED-DEFERRED`, `DO NOT IMPLEMENT`. **No matches.** `_index.md:3` reads `**Status:** design complete, ready for plan-writing.` JUST-01 PASS.

## Checklist Results

| Item ID | Check | Result | Evidence |
|---|---|---|---|
| JUST-01 | Justification marker absent | PASS | `_index.md:3` |
| DESIGN-STRUCTURE-01 | Required section order | PASS | Context (L7), Discovery Results (L22), Requirements (L55), Rationale (L82), Detailed Design (L94), Design Documents (L102). Glossary at L38 is a non-required addition. |
| DESIGN-STRUCTURE-02 | Folder name format | PASS | `2026-05-27-agentbook-outcome-loop-design`. |
| DESIGN-STRUCTURE-03 | Four files present | PASS | _index.md, bdd-specs.md, architecture.md, best-practices.md all exist. |
| DESIGN-BDD-01 | Every requirement maps to ≥1 scenario | **FAIL** | R7 (`evaluate_offline_rotate`) has zero Gherkin coverage; R6 (orchestrator chain scheduling) only implicitly at L264-269. |
| DESIGN-BDD-02 | Error paths have scenarios | PASS | Malformed JSON, empty root_cause, TimeoutExpired, under-evidenced, empty log, test-file refusal. |
| DESIGN-BDD-03 | DoS/resilience gates have scenarios | PASS | scrub_leak, idempotency, timeout isolation, min_failure_count, 6-strike. |
| DESIGN-BDD-04 | Migration scenarios | PASS | Lazy revision-0 backfill at runtime; malformed JSON leaves prior revisions untouched. |
| DESIGN-CONSISTENCY-01 | Numeric values consistent across files | **FAIL** | `bdd-specs.md:1` claims "26 scenarios"; `_index.md:105` claims sum=26 from "(10 refinement, 9 parser, 7 rotation)". Actual count is 32 (10 + 10 + 5 + 7). |
| DESIGN-CONSISTENCY-02 | Policy-location claims enforced in BDD | PASS | `_pick_unexplored` shared by both routers via L249 (Rule/KNN disagree); test-file refusal preserved L168; `select_arms` unchanged L257. |
| DESIGN-SCOPE-01 | Requirements trace to user-confirmed scope | PASS | `_index.md:20` names directions A/C explicit; B/D/E deferred at L74-80. |
| DESIGN-SCOPE-02 | Rationale justifies each numeric threshold | **FAIL** | `min_failure_count=3` (appears 8×) and `max_turns_per_run=4` lack numeric justification. `--max-tasks 10` justified only by analogy. |
| DESIGN-REFERENCE-01 | External references re-verified | PASS | No external URLs. |
| DESIGN-SPECIFICITY-01 | Exact paths/signatures | PASS | File Map L9-25, every new function has a signature with types. |
| DESIGN-SPECIFICITY-02 | Migration uses exact SQL/Alembic ops | PASS | N/A — JSON file storage; lazy revision-0 backfill is the migration code. |

## Rework Items

1. **DESIGN-BDD-01**: Add Gherkin coverage for R7 (`evaluate_offline_rotate`) — at least one scenario asserting "coverage ≥ static best-arm at k=3 under LOO". Add a scenario for R6 (orchestrator serial-within-chain invariant).
2. **DESIGN-CONSISTENCY-01**: Update `bdd-specs.md:1` and `_index.md:105` to the actual count of 32 scenarios with the breakdown (10 + 10 + 5 + 7).
3. **DESIGN-SCOPE-02**: Add a "Numeric thresholds" paragraph to Rationale justifying `min_failure_count=3`, `max_turns_per_run=4`, `--max-tasks 10` numerically.

## Verdict

**REWORK** — 3 FAILs, all fixable in one pass without architectural change.
