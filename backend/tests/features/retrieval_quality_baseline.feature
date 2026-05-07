Feature: Retrieval quality baseline

  As an agentbook contributor changing retrieval logic
  I want a frozen quality baseline (recall@k, MRR, nDCG, no-false-exact rate)
  So that silent regressions in search ranking are caught in CI before merge

  Background:
    Given the agentbook service uses in-memory repositories
    And conftest forces fallback embedding plus noop reranker
    And the corpus is seeded from PROBLEM_TEMPLATES (15 problems) in list-index order
    And the eval dataset retrieval_quality_dataset.json (65 queries) is loaded

  Scenario: Baseline collection prints metrics without asserting
    Given the environment variable EVAL_BASELINE_MODE is "collect"
    When the harness runs all 65 queries against search_problems
    Then per-query and aggregate metrics are printed
    And a JSON block ready to paste into docs/retrieval-baseline.md is printed
    And the test is reported as skipped after printing

  Scenario: Regression guard catches a 5-point drop in any guarded metric
    Given the environment variable EVAL_BASELINE_MODE is "guard"
    And docs/retrieval-baseline.md contains a frozen JSON aggregate block
    When the harness runs all 65 queries
    Then current recall@1, recall@5, recall@10, MRR, and binary nDCG@10
         are within 5 absolute points of the frozen baseline
    And no_false_exact_rate is greater than or equal to the frozen baseline
    And latency p95 is at most 2x the frozen baseline p95
    And the test fails listing per-metric drift on regression

  Scenario: Cross-topic confusion does not earn match_quality "exact" on a non-target
    Given a query containing keywords from two unrelated templates
    When search_problems is called with limit 10
    Then no result outside expected_template_indices is tagged "exact"
    And the no_false_exact_ok flag for the query is true

  Scenario: Out-of-corpus query returns no high-quality match
    Given a query about a topic not present in PROBLEM_TEMPLATES
    When search_problems is called with limit 10
    Then either the result list is empty
    Or no result is tagged "exact" or "strong"

  Scenario: Robustness — empty, single-token, or 500+ char queries do not crash
    Given a query that is empty, one character, or a 500+ character noise string
    When search_problems is called with limit 10
    Then no exception is raised
    And the harness records the result without contributing to recall/MRR aggregates
