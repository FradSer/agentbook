Feature: Autonomous research loop

  Scenario: Cold-start bootstrapping
    Given a problem with one solution at confidence 0.25
    When the researcher proposes an improvement
    Then the new solution has confidence 0.3
    And the existing solution is marked as superseded

  Scenario: Research prompt includes outcome signal
    Given a solution with 3 outcomes (2 success, 1 failure)
    When the research prompt is built
    Then the prompt contains success/failure counts and failure notes

  Scenario: Bloat filter rejects verbose proposals
    Given a solution with 100 chars at confidence 0.5
    When an improvement with 250 chars is proposed at confidence 0.51 (gain <= 0.05)
    Then the proposal is rejected with status no_improvement

  Scenario: Bloat filter allows verbose proposals with significant gain
    Given a solution with confidence 0.3
    When an improvement with 2x+ length is proposed with confidence 0.5
    Then the proposal is accepted (gain 0.2 exceeds 0.05 threshold)

  Scenario: Agent calls tool directly (no text parsing)
    Given a problem with a low-confidence solution
    When the agent calls skip_improvement tool
    Then the response contains "Status: no_improvement"
    And no manual service.improve_solution call is made

  Scenario: Agent calls propose_improvement tool directly
    Given a problem with a low-confidence solution
    When the agent calls propose_improvement tool
    Then the response contains "Status: improved"
    And the new solution confidence is 0.3

  Scenario: Synthesis via service method only
    Given a problem with 2 active solutions
    When synthesize_solutions is called with a synthesized content
    Then a canonical solution is created
    And both source solutions are marked as superseded
    And the canonical solution id is returned

  Scenario: Synthesis distils transferable structured knowledge from prose
    Given a problem with 2 active prose-only solutions
    When the synthesis LLM returns canonical content plus root-cause, cues and verification
    Then synthesize_structured_knowledge parses all four fields from the reply
    And synthesize_solutions stamps the generated knowledge onto the canonical solution
    And the generated knowledge overrides the union merged from the sources

  Scenario: skip_improvement records a research cycle for cooldown
    Given a problem with one solution
    When the researcher calls skip_improvement
    Then a ResearchCycle with status "no_improvement" is recorded
    And the problem is excluded from candidates within cooldown period

  Scenario: solution_count increments on accepted improvement
    Given a problem with best_confidence 0.8 and solution_count 3
    When an improvement beats the incumbent (0.3 -> 0.5) but not best (0.8)
    Then solution_count increments to 4

  Scenario: cooldown filtering returns full requested count
    Given 20 problems where 15 are in cooldown
    When find_research_candidates is called with limit=5
    Then exactly 5 candidates are returned
