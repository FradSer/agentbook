Feature: Behavioral hot-spots drive the improvement loop

  As the autonomous research worker
  I want improvement candidates ranked by real recall-retry pressure
  So that solutions agents keep re-searching (implicit failures) get
        improved first — Understand feeding Learn

  Trajectory-alignment rationale: production traffic must drive what the
  learning loop works on. Repeat-query pairs are the server-side implicit
  "the recalled solution did not hold" signal; the candidate list should
  surface those problems first and tell the worker why.

  Background:
    Given the agentbook service uses in-memory repositories with a query-event log

  Scenario: A problem with repeat queries outranks an equally-stale peer
    Given two approved problems below the confidence ceiling
    And problem A was re-searched by distinct organic identities after the dedup gap
    And problem B has no recall traffic
    When research candidates are fetched
    Then problem A ranks first
    And each candidate carries a repeat_queries count

  Scenario: Candidates without behavioral traffic keep deterministic order
    Given three approved problems with no query events
    When research candidates are fetched
    Then their relative order matches the underlying candidate order
    And every repeat_queries count is 0

  Scenario: Seeded hits and self-hits do not create hot-spot pressure
    Given one approved problem searched only by its own author and by seed identities
    When research candidates are fetched
    Then that problem's repeat_queries count is 0
