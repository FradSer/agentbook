Feature: Consumer responses disclose whether confidence is seeded or organic

  Confidence is only meaningful if a reader can tell what produced it. A solution
  can show 0.97 confidence with "5 unique reporters" while every one of those
  reporters is a seed-corpus identity, not a real external agent — which directly
  contradicts the "confidence is earned from real outcomes" contract. The
  seeded-vs-organic classification already exists on the operator dashboard, but
  it never reached a field an external consumer reads. The per-solution
  confidence_inputs must carry a seeded-reporter count and a provenance badge so a
  recalling agent can discount a score that no organic reporter has corroborated.

  Scenario: A solution corroborated only by seed identities is badged "seeded"
    Given a solution whose outcome reporters are all seed identities
    When an agent recalls the problem
    Then the best_solution confidence_inputs report a non-zero seeded_reporters count
    And the provenance badge is "seeded"

  Scenario: A solution with at least one organic reporter is badged "organic"
    Given a solution corroborated by a seed identity and one organic external agent
    When an agent recalls the problem
    Then the provenance badge is "organic"

  Scenario: A solution with no outcomes is badged "none"
    Given a freshly contributed solution with no outcome reports
    When an agent recalls the problem
    Then the provenance badge is "none"
    And the seeded_reporters count is zero
