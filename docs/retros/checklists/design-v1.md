# Design Mode Checklist — v1

Initial seed distilled from the 2026-04-18 memory-layer-autoresearch plan. Binary PASS/FAIL items the evaluator (brainstorming skill) applies against `_index.md`, `bdd-specs.md`, and the companion design docs before the design is committed.

## Required structure

- **DESIGN-STRUCTURE-01**: `_index.md` has these section headings in this order: Context, Discovery Results, Requirements, Rationale, Detailed Design, Design Documents.
- **DESIGN-STRUCTURE-02**: Folder name ends in `-design` and starts with an ISO date (`YYYY-MM-DD-<topic>-design`).
- **DESIGN-STRUCTURE-03**: For Complex designs: all four files present — `_index.md`, `bdd-specs.md`, `architecture.md`, `best-practices.md`.

## BDD coverage

- **DESIGN-BDD-01**: Every Requirement (R1..RN) in `_index.md` maps to ≥1 Gherkin scenario in `bdd-specs.md`.
- **DESIGN-BDD-02**: Every feature with non-trivial error paths has scenarios for the error path, not only the happy path.
- **DESIGN-BDD-03**: Every DoS / resilience / rate-limit gate explicitly asserted in `best-practices.md` has a matching scenario (timeout, budget exhaustion, dedup, circuit breaker).
- **DESIGN-BDD-04**: Zero-downtime migration designs include scenarios for mid-run failure, rollback, and pre-flight guard.

## Consistency across files

- **DESIGN-CONSISTENCY-01**: Numeric ratios, multipliers, and sentinel values referenced in `_index.md` are identical in `bdd-specs.md`, `architecture.md`, and `best-practices.md`.
- **DESIGN-CONSISTENCY-02**: Policy-location claims (e.g. "this logic lives in X not Y") are enforced in at least one BDD scenario.

## Scope and rationale

- **DESIGN-SCOPE-01**: Every requirement traces to a user-confirmed scope item (AskUserQuestion answer or explicit brief).
- **DESIGN-SCOPE-02**: Rationale section justifies each numeric threshold or cutoff (not just "because we chose").

## Reference freshness

- **DESIGN-REFERENCE-01**: External references older than 14 days relied on for decisive architectural decisions carry a re-verification task in the Discovery Results or an explicit note that the implementation plan must schedule one.

## Executable specificity

- **DESIGN-SPECIFICITY-01**: Interface changes specify exact file paths and function signatures (not prose descriptions).
- **DESIGN-SPECIFICITY-02**: Migration plans include exact SQL or Alembic op names.
