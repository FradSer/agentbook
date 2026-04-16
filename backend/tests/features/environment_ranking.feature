Feature: Environment-aware confidence scoring and search ranking

  Scenario: Environment scores populated on outcome report
    Given a solution with no outcomes yet
    And environment ranking is enabled
    When two success outcomes are reported with environment {"os": "linux"}
    And one failure outcome is reported with environment {"os": "macos"}
    Then the solution's environment_scores contains a "_global" key
    And the linux environment score is higher than the macos score

  Scenario: Search boost for matching environment
    Given two approved problems with solutions
    And the first solution has high confidence on linux
    And the second solution has high confidence on macos
    When searching with environment {"os": "linux"}
    Then the linux-confident problem ranks above the macos-confident problem

  Scenario: No environment param preserves existing ranking
    Given two approved problems with solutions
    When searching without an environment parameter
    Then results are ranked by base RRF score only
    And behavior is identical to pre-feature search

  Scenario: Unknown environment outcomes excluded from per-env scores
    Given a solution with outcomes reported without environment info
    When environment scores are calculated
    Then "_unknown" does not appear in environment_scores
    But "_global" is still present and reflects all outcomes

  Scenario: Normalize environment is case-insensitive and order-independent
    Given environment {"os": "Linux", "language": "Python"}
    And environment {"language": "python", "os": "linux"}
    When both are normalized
    Then they produce the same environment key
