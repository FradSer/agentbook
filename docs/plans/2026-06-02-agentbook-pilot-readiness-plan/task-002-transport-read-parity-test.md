# Task 002 (transport-read-parity) — Test (Red)

**type:** test
**theme:** P0-A
**closes:** PR-1
**depends-on:** [001]

## Goal

Write the failing (Red) BDD tests for the **Transport parity for the read contract** behavior. These tests encode the target contract and MUST fail against current `main` before the paired impl task (002-transport-read-parity-impl) makes them pass.

## BDD Scenarios (source of truth)

```gherkin
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

---
```

## Files

- `backend/tests/features/transport-read-parity.feature` — the Gherkin above, verbatim.
- `backend/tests/unit/test_transport_read_parity.py` — step implementations / assertions. Isolate external dependencies (DB, Voyage, network) with in-memory repos and test doubles per `backend/tests/conftest.py` conventions; use the `enable_limiter` fixture only where a scenario asserts rate-limit behavior.

## Steps

1. Copy the scenarios above into `transport-read-parity.feature`.
2. Implement step defs / test functions asserting the target contract (NOT current behavior). For cross-transport parity scenarios, assert REST and MCP payloads field-by-field via a shared helper.
3. Run the tests; confirm they FAIL (Red) for the documented reason (current behavior diverges).

## Verification

```bash
uv run pytest backend/tests/unit/test_transport_read_parity.py -q   # expect FAIL (Red) before impl
```
