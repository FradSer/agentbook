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
          beneath the "## Frozen aggregate" heading
    When the harness runs all 65 queries
    Then current recall@1, recall@5, recall@10, MRR, and binary nDCG@10
         are within 5 absolute points of the frozen baseline
    And no_false_exact_rate is greater than or equal to the frozen baseline
    And latency p95 is at most max(2x baseline, 50ms) so sub-millisecond
        runner noise does not cause spurious flakes
    And the test fails listing per-metric drift on regression

  Scenario: Dataset version mismatch is rejected before any drift check
    Given the dataset_version in retrieval_quality_dataset.json
    And the dataset_version in the frozen baseline JSON block
    When the two values differ
    Then the harness hard-fails with a "Dataset version mismatch" error
    And no recall, MRR, nDCG, or latency comparison is performed

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

  Scenario: Real-mode opt-in eval guards the Voyage retrieval stack independently
    Given the environment variable RUN_REAL_EVAL is "1"
    And VOYAGE_API_KEY is set to a valid Voyage AI credential
    And docs/retrieval-baseline.md contains a non-placeholder JSON block
          beneath the "## Frozen aggregate (real-mode)" heading
    When the harness runs all 65 queries through the real Voyage pipeline
    Then the same regression tolerances apply as fallback mode
    And dataset_version must match the real-mode baseline exactly
    And no fallback-mode metric is altered

  Scenario: Real-mode opt-in eval refuses to run without VOYAGE_API_KEY
    Given the environment variable RUN_REAL_EVAL is "1"
    And VOYAGE_API_KEY is unset
    When the harness loads
    Then the test is skipped with a "requires VOYAGE_API_KEY" message
    And no metrics are collected
