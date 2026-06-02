# Task 012 (confidence-legibility) — Impl (Green)

**type:** impl
**theme:** P1-D
**closes:** PR-12, PR-7
**depends-on:** [012-confidence-legibility-test, 002-transport-read-parity-impl]

## Goal

Make the Red tests from 012-confidence-legibility-test pass. Carry the structured confidence provenance the FROZEN math already computes onto every read surface (`confidence_inputs`, `confidence_capped_by`, `external_reporters_for_full_confidence`, optional machine-readable `confidence_note`) so a 0.3/0.5 read is self-explanatory. Signal outcome re-report as replace vs append (`replaced: true` or HTTP 200) so an agent can reconstruct its own history (PR-7). No math change.

Clean Architecture discipline: keep business logic in `AgentbookService`; Presentation layers only serialize. Do NOT bump `confidence.py:__frozen_policy_version__` — every confidence-related change here only *surfaces* values the frozen math already computes.

## BDD Scenarios (target behavior)

```gherkin
Feature: Confidence legibility on the outcome report write contract

  An outcome report's response must let an agent read WHY confidence is capped
  from structured fields, not only from prose. The agent must be able to
  distinguish the cold-start floor, the author-self-report rule, and the
  external-reporter threshold programmatically.

  Scenario: Capped report carries machine-readable provenance
    Given a solution with one external confirming report
    When an agent reports a second external success
    Then the response carries confidence_capped_by "cold_start_floor"
    And external_reporters 2 and external_reporters_for_full_confidence 3
    And confidence_delta 0.0 with a confidence_note explaining "2 of 3 distinct external reporters so far"
    So a delta of 0.0 is interpretable as "held at the floor", not "report lost"

  Scenario: Author self-report is legibly inert
    Given an author reports success on their own solution
    Then confidence_delta is 0.0 and external_reporters is 0
    And confidence_note states the author's own reports never move confidence

  Scenario: Floor release is legible
    Given a solution with two external confirming reports
    When a third distinct external reporter confirms success
    Then confidence_capped_by becomes null
    And confidence_delta is positive
    And the jump is explained by external_reporters reaching the threshold

  Scenario: Re-report signals replace versus append
    Given an agent already reported an outcome on a solution
    When the same agent reports a different outcome on the same solution
    Then the response indicates the prior report was replaced (e.g. replaced true, or HTTP 200 not 201)
    And outcome_count stays 1 for that reporter-solution pair

---
```

## Files

- `backend/application/service.py`

## Interface contract (signatures only — no implementation bodies)

```python
# Application: read-surface provenance + replace signal on re-report
# report_outcome(...) -> {..., 'replaced': bool}
```

## Steps

1. Implement the change described above across the listed files, matching surrounding code style (Ruff, 88 cols, double quotes).
2. Keep both transports calling shared Application logic where applicable (no per-transport business logic).
3. Run the paired test file; confirm GREEN. Run `make fast` to confirm no regressions.

## Verification

```bash
uv run pytest backend/tests/unit/test_confidence_legibility.py -q   # expect PASS (Green)
make fast                                                   # no regressions
```
