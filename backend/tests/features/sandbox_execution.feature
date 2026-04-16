Feature: Sandbox execution for cold-start improvement evaluation

  Scenario: Executable solution validated by sandbox accepts improvement
    Given an existing solution with no outcomes and a Python code block
    And a proposed improvement with a Python code block that runs successfully
    And the LLM evaluator is unavailable
    When the sandbox runs both solutions
    And the proposed solution succeeds while the existing fails
    Then the improvement is accepted with reason "cold_start_sandbox_better"

  Scenario: Sandbox rejects improvement when proposed fails
    Given an existing solution with executable code that succeeds
    And a proposed improvement with executable code that fails
    And the LLM evaluator is unavailable
    When the sandbox runs both solutions
    Then the improvement is rejected with reason "cold_start_sandbox_no_improvement"

  Scenario: Non-executable solution falls through to content heuristic
    Given an existing solution with only instructional text
    And a proposed improvement with only instructional text
    And both the LLM evaluator and sandbox are available
    When _extract_executable_code returns None for both
    Then sandbox_score is None
    And the content quality heuristic decides acceptance

  Scenario: LLM evaluator takes precedence over sandbox
    Given the LLM evaluator returns a score
    And the sandbox would return a different verdict
    When evaluate_improvement is called with both scores
    Then the evaluator score determines the outcome
    And the sandbox score is ignored

  Scenario: Accepted solution gets post-acceptance sandbox outcome
    Given an improvement is accepted during cold-start
    And the sandbox provider is configured
    When the improvement pipeline completes
    Then a synthetic outcome is recorded with the sandbox agent ID
    And the outcome weight is 0.3
