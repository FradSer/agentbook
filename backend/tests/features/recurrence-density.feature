Feature: Recurrence-density instrument

  Recurrence density is the single variable that decides whether a shared memory
  layer has a market: the fraction of independent incoming queries whose top hit
  is an actionable existing entry contributed by someone other than the querier.
  The instrument records one QueryEvent per recall (best-effort, side-channel)
  and rolls those events into recurrence_density and organic_recurrence.

  For the number to be trustworthy it must count real traffic faithfully:
  distinct callers must each count, a querier's hit on their own entry must not,
  seed-replay must not, and a result served from the latency cache must still be
  recorded — otherwise the cache silently hides exactly the cross-agent repeat
  traffic that organic recurrence is meant to measure.

  Scenario: A recalled search records one event counted by the rollup
    Given an approved problem with one active solution matchable by its error signature
    When a non-author agent recalls it
    Then exactly one query-event is recorded with a strong-or-exact top match and a reliance target
    And the rollup reports total_independent_queries 1 and recurrence_density above zero

  Scenario: A querier's hit on its own entry is recorded but excluded from the numerator
    Given an approved problem with one active solution matchable by its error signature
    When the problem's own author recalls it
    Then the event is flagged a self-hit
    And recurrence_density stays 0.0

  Scenario: A no-good-match recall counts only toward the denominator
    Given a book with no entry matching the query
    When an agent recalls an unrelated query
    Then the event records no top match and no reliance target
    And total_independent_queries is 1 with recurrence_density 0.0

  Scenario: Recording never breaks a search
    Given a query-events backend that raises on write
    When an agent recalls a matchable query
    Then the search still returns its normal payload
    And the swallowed recording error is logged, not re-raised

  Scenario: Distinct callers issuing the same cached query each count
    Given an approved problem matchable by a query whose result is cached after the first recall
    When a second, different agent recalls the identical query within the cache window
    Then the cache serves the response but the second caller still records its own query-event
    And the rollup counts two independent queries, not one
