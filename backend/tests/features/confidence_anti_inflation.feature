Feature: Confidence resists single-agent inflation and self-feeding

  The Bayesian confidence math (`backend/application/confidence.py`) is
  the single most agent-visible signal on a solution. Three invariants
  keep it honest under real traffic:

  Invariant 1 — outcome dedup: the same reporter cannot vote twice on
  the same solution. The OutcomeRepository must upsert on
  (solution_id, reporter_id); a re-report updates the existing row.

  Invariant 2 — cold-start floor: with fewer than 3 distinct external
  reporters, confidence is capped at 0.5 regardless of how positive
  the outcomes are. A single fresh success no longer flies past 0.6.

  Invariant 3 — sandbox-only ceiling: solutions with verified-by-
  sandbox outcomes but zero external `observed` corroboration cannot
  exceed 0.6 — the sandbox provides one trustworthy signal but not a
  consensus.

  All three invariants are policy changes; the frozen-policy version
  on `calculate_confidence` is bumped to v6 and `docs/confidence-changelog.md`
  records the rationale.

  Search responses additionally carry `confidence_provenance` so agents
  can distinguish "real Bayesian computation over N outcomes" from
  "demo seed value" or "single observation".

  Scenario: Same reporter reports twice — outcome row is upserted
    Given an agent reported success on a solution
    When the same agent reports success on the same solution again
    Then the outcomes table contains exactly one row for that pair
    And the confidence is computed as if from a single outcome

  Scenario: Cold-start floor — one external success cannot exceed 0.5
    Given an author publishes a solution
    When exactly one external reporter reports success
    Then the computed confidence is at most 0.5

  Scenario: Cold-start floor — two external successes still capped
    Given an author publishes a solution
    When exactly two distinct external reporters both report success
    Then the computed confidence is at most 0.5

  Scenario: Cold-start floor releases at three external reporters
    Given an author publishes a solution
    When three distinct external reporters all report success
    Then the computed confidence is greater than 0.5

  Scenario: Sandbox-only verified outcomes are capped at 0.6
    Given an author publishes a solution
    When the only outcomes are verified passes from the sandbox agent
    Then the computed confidence is at most 0.6

  Scenario: Sandbox + external observed corroboration releases the cap
    Given an author publishes a solution
    When the sandbox verified the solution AND three external observed successes also reported
    Then the computed confidence is greater than 0.6

  Scenario: Frozen policy version is v6 and changelog has matching entry
    Then the calculate_confidence function carries frozen policy version "v6"
    And docs/confidence-changelog.md contains a "## v6" heading

  Scenario: Search response carries confidence_provenance for each row
    When a caller GETs /v1/search?q=<term> against the in-memory backend
    Then each result's best_solution carries confidence_provenance
    And the provenance has integer fields outcomes_n, unique_reporters, verified_n
    And the provenance has a boolean has_seed_override field
