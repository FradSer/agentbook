Feature: LRU TTL cache for search results

  Scenario: Identical queries within TTL return cached payload without recomputing
    Given a search service backed by in-memory repositories
    When the same query is issued twice within the TTL window
    Then the second call returns the same payload object as the first
    And the underlying search is computed only once

  Scenario: Cached payload expires after TTL elapses
    Given a search service with a cache TTL of 300 seconds
    When the clock advances past the TTL
    Then the next identical query recomputes the result

  Scenario: Different queries produce different cache entries
    Given a search service with an empty cache
    When two different queries are issued
    Then both results are cached independently

  Scenario: Cache key distinguishes include and format params
    Given a search service with an empty cache
    When the same q is issued with include=solutions then again without include
    Then the two payloads are cached under distinct keys

  Scenario: LRU eviction drops oldest entries over maxsize
    Given a cache with maxsize=2
    When three distinct queries are issued in order A, B, C
    Then A is evicted and B and C remain
