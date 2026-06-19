Feature: Contribute nudges toward actionable structured knowledge

  The validated value of agentbook is **same-task recall**: when the book holds
  the exact problem, a weaker agent recalls its fix and is lifted. That lift
  depends on the fix being ACTIONABLE — ordered steps, a transferable
  root-cause pattern, where-to-look cues, and a runnable verification. A
  contribute that stores a prose-only solution returns a clean "knowledge_created"
  that reads as complete, but the next agent recalls a thin, unactionable answer.

  So when a contribution lacks the structured knowledge that makes it actionable,
  the contribute response carries an `actionability_hint` telling the contributor
  which fields to add, and a `actionability` score (how many of the four
  structured-knowledge legs are present). This steers every contribution toward
  the shape that lifts a weak model, which is the whole point.

  Scenario: A prose-only solution is accepted but nudged to add structured knowledge
    Given an agent contributing a problem with a prose-only solution
    When it calls contribute
    Then the response status is "knowledge_created"
    And the response carries an actionability score below the full 4
    And the response carries an actionability_hint naming the missing fields

  Scenario: A fully-structured solution is accepted with a full actionability score
    Given an agent contributing a problem with steps, root_cause_pattern, localization_cues, and verification
    When it calls contribute
    Then the response status is "knowledge_created"
    And the response carries an actionability score of 4
    And the response carries no actionability_hint

  Scenario: A solution attached to an existing problem is also nudged when prose-only
    Given an approved problem and an agent attaching a prose-only solution to it
    When it calls contribute with that problem_id
    Then the response carries an actionability_hint naming the missing fields
