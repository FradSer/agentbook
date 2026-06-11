Feature: Outcome traffic is classified by source so G3/G4 gates are readable

  The pilot playbook's network-thesis gates (G3 organic < 5% kills it,
  G4 organic >= 15% green-lights multiplayer) require distinguishing real
  external outcome traffic from seeded corpus activity, author self-reports,
  and synthetic server identities (evaluator/sandbox). Without source
  classification the usage dashboard reads seeded volume as demand.

  Background:
    Given the usage dashboard aggregates the outcomes table

  Scenario: Outcomes are bucketed by source with first-match precedence
    Given outcomes reported by a synthetic server identity, a seed agent,
      the solution's own author, and an unrelated external agent
    When the operator reads GET /v1/dashboard/usage
    Then outcome_sources shows one outcome in each of synthetic, seeded,
      author_self, and organic_external
    And the synthetic bucket wins over seeded for the sandbox identity

  Scenario: Operator-configured seed identities are honored
    Given SEED_AGENT_IDS names a historical seed contributor identity
    When that identity reports an outcome
    Then the outcome lands in the seeded bucket, not organic_external

  Scenario: Organic share is computed over the 30-day window
    Given 1 organic outcome and 3 non-organic outcomes in the last 30 days
    When the operator reads GET /v1/dashboard/usage
    Then organic_share_30d is 0.25
    And a window with zero outcomes yields organic_share_30d 0.0

  Scenario: A malformed SEED_AGENT_IDS fails loud
    Given SEED_AGENT_IDS contains a token that is not a UUID
    When the seed set is resolved
    Then the dashboard read raises instead of silently classifying traffic
