Feature: Enriched search results via include and format

  Scenario: Concise search omits enrichment by default
    Given an approved problem with one approved solution
    When /v1/search is called with no include parameter
    Then each result has no solutions field
    And each result has no outcomes field
    And each result has no lineage field

  Scenario: include=solutions returns the full solution list per result
    Given an approved problem with two approved solutions
    When /v1/search is called with include=solutions
    Then each result has a solutions list containing both solutions

  Scenario: include=outcomes returns outcomes for the best solution
    Given an approved problem whose best solution has two outcomes
    When /v1/search is called with include=outcomes
    Then each result has an outcomes list containing both outcomes

  Scenario: include=lineage returns the parent chain of the best solution
    Given an approved problem whose best solution supersedes an older solution
    When /v1/search is called with include=lineage
    Then each result has a lineage list starting from the oldest ancestor

  Scenario: format=full returns complete solution content
    Given an approved problem with a best solution longer than 200 characters
    When /v1/search is called with format=full
    Then the best_solution content is not truncated

  Scenario: format=concise keeps the preview truncated
    Given an approved problem with a best solution longer than 200 characters
    When /v1/search is called with format=concise
    Then the best_solution content_preview is at most 200 characters

  Scenario: Multiple include values can be combined
    Given an approved problem with solutions, outcomes, and lineage
    When /v1/search is called with include=solutions,outcomes,lineage
    Then each result has all three enrichment fields populated
