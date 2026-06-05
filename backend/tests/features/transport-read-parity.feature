Feature: Transport parity for the read contract

  The differentiating asset of the memory layer is transferable structured
  knowledge (root_cause_pattern, localization_cues, verification) plus
  confidence provenance (confidence_inputs, outcome_count). The same logical
  recall operation must return the SAME per-solution fields over both
  transports (REST /v1/search and MCP recall) so an agent can switch transport
  without re-learning the payload or paying a second round-trip. Today the REST
  read contract silently drops structured knowledge and confidence provenance
  that MCP recall exposes inline.

  A single shared read-payload builder backs both transports; neither path may
  serialize a richer or poorer best_solution than the other.

  Scenario: REST search and MCP recall return identical best_solution fields
    Given a problem with one solution carrying root_cause_pattern, localization_cues, and verification
    When an agent recalls it over REST GET /v1/search?q=<term>
    And an agent recalls the same query over MCP recall
    Then both best_solution payloads expose the keys root_cause_pattern, localization_cues, verification, root_cause_class, outcome_count, and confidence_inputs
    And the values for those keys are equal across the two transports

  Scenario: REST search exposes confidence provenance like MCP recall
    Given a solution whose confidence was computed from real outcomes
    When an agent recalls it over REST GET /v1/search
    Then best_solution.confidence_inputs carries integer outcomes_n, unique_reporters, verified_n
    And best_solution.confidence_inputs carries a boolean has_seed_override
    And the agent can read why the confidence is what it is without a second round-trip to GET /v1/problems/{id}

  Scenario Outline: Structured-knowledge keys are present even when empty
    Given a solution with no structured knowledge attached
    When an agent recalls it over <transport>
    Then best_solution contains the key "<field>" with a null or empty value
    And the key is never silently omitted

    Examples:
      | transport       | field              |
      | REST /v1/search | root_cause_pattern |
      | REST /v1/search | localization_cues  |
      | REST /v1/search | verification       |
      | MCP recall      | root_cause_pattern |
      | MCP recall      | localization_cues  |
      | MCP recall      | verification       |

  Scenario: Preview truncation is flagged, not silent
    Given a solution whose full content is longer than the preview budget
    When an agent recalls it over either transport
    Then content_preview is truncated on a clean boundary, not mid-word
    And the payload carries a boolean content_truncated set to true
    And a full "content" field is retrievable on the read contract without a separate trace call

  # The recurrence-density instrument records one QueryEvent per recall as a
  # side-channel (the response payload is unchanged). For the instrument to
  # measure real traffic, both transports must stamp the event with the caller's
  # identity. Today only MCP recall does; REST /v1/search records an anonymous
  # caller-less event, so same-IP REST traffic collapses to one query and
  # organic recurrence can never be attributed.
  Scenario: REST search stamps the recurrence query-event with caller identity
    Given a problem with one solution matchable by an error signature
    When an authenticated agent recalls it over REST GET /v1/search
    Then the recorded query-event carries that agent's id, ip_hash, and fingerprint_hash
    And the recall response payload is unchanged by the recording

  Scenario: Anonymous REST search records a dedup-capable ip_hash like MCP recall
    Given a problem with one solution matchable by an error signature
    When an anonymous client recalls it over REST GET /v1/search
    Then the recorded query-event has agent_id null and a non-null ip_hash derived from the remote address
    And two anonymous REST searches from one address collapse to a single independent query

---
