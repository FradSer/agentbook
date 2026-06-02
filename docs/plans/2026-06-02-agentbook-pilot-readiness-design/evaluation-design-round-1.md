# Design Evaluation Report — agentbook-pilot-readiness

**Mode:** Design
**Folder:** `docs/plans/2026-06-02-agentbook-pilot-readiness-design/`
**Checklist:** `docs/retros/checklists/design-v2.md`

## JUST-01 Pre-check

No `NOT-JUSTIFIED` / `DESIGN-CONSIDERED-DEFERRED` / `DO NOT IMPLEMENT` marker found in `_index.md` (grep across all design files returned zero matches). JUST-01 does not apply; verdict is driven by content-quality items below.

## Checklist Results

| Item ID | Check | Result | Evidence |
|---|---|---|---|
| DESIGN-STRUCTURE-01 | Required headings present in order | PASS | Headings in order: Context, Discovery Results, Requirements, Rationale, Detailed Design, Design Documents. An extra `Glossary` sits between Discovery and Requirements; the six required headings remain in the mandated relative order. |
| DESIGN-STRUCTURE-02 | Folder name `YYYY-MM-DD-<topic>-design` | PASS | `2026-06-02-agentbook-pilot-readiness-design`. |
| DESIGN-STRUCTURE-03 | All four files present (Complex) | PASS | `_index.md`, `bdd-specs.md`, `architecture.md`, `best-practices.md` all present. |
| DESIGN-BDD-01 | Every requirement maps to ≥1 Gherkin scenario | **FAIL → fixed round 2** | PR-3 (cross-transport rejection parity) and PR-18 length-floor leg had no scenario. Both added in round 2 (see below). |
| DESIGN-BDD-02 | Error-path scenarios, not only happy path | PASS | 422 unknown-field, auth no-key/bad-key, `not_found`, `-32601`, `-32700`. |
| DESIGN-BDD-03 | DoS/resilience/rate-limit gates have scenarios | PASS | Latency/timeout degrade, boot-misconfig fail-loud, write-time dedup; rate-limit assertions catalogued as proven strengths (do-not-touch). |
| DESIGN-BDD-04 | Zero-downtime migration scenarios | PASS (N/A) | Only migration is an additive nullable `gate_reason` column; no zero-downtime cutover. |
| DESIGN-CONSISTENCY-01 | Numeric values identical across files | PASS | `45` total, `0.3/0.5/0.962`, `3 external reporters`, `9/20` orphans, `v6` consistent across all files. |
| DESIGN-CONSISTENCY-02 | Policy-location claims enforced by ≥1 scenario | PASS | FROZEN-math surface-only enforced by read-path-echoes scenarios; shared-builder claim enforced by identical-fields scenario. |
| DESIGN-SCOPE-01 | Every requirement traces to confirmed scope | PASS | All 18 PRs cite the specific finding(s) they close. |
| DESIGN-SCOPE-02 | Rationale justifies each numeric threshold | PASS | `<1s` budget, cold-start floor, P0/P1/P2 tiering all justified. |
| DESIGN-REFERENCE-01 | Stale external refs carry re-verification task | PASS (N/A) | All decisive refs are internal `file:line`; the v5→v6 staleness is flagged, not relied upon. |
| DESIGN-SPECIFICITY-01 | Interface changes give exact paths + signatures | PASS | Named typed fields, `ConfigDict(extra="forbid")`, `_resolve_book_solution` promotion, `voyageai.Client` timeout, unified read-row JSON schema. |
| DESIGN-SPECIFICITY-02 | Migration plans give exact SQL / Alembic op | PASS (weak) | Additive nullable `gate_reason` via `alembic revision --autogenerate`. |

## Rework Items (resolved in round 2)

| Item ID | Location | What failed | Corrective action taken |
|---|---|---|---|
| DESIGN-BDD-01 | PR-3 | No scenario for gate-rejection signaling identical across REST (409) and MCP (200+isError). | Added Feature "Transport parity for rejection signaling" to `bdd-specs.md`. |
| DESIGN-BDD-01 | PR-18 length-floor leg | "solution-too-short error states the threshold" leg unscenarioed. | Added scenario to the contribute feature asserting the error states the minimum, mirroring the description validator. |

## Verdict (round 1)

**REWORK** — 1 failing checklist item (DESIGN-BDD-01), 2 coverage gaps. The design is strong on grounding, consistency, and executable specificity; the only blocker was BDD coverage. Both scenarios added in round 2; see `evaluation-design-round-2.md` for the confirming verdict.
