# Task 002 (transport-read-parity) — Impl (Green)

**type:** impl
**theme:** P0-A
**closes:** PR-1
**depends-on:** [002-transport-read-parity-test]

## Goal

Make the Red tests from 002-transport-read-parity-test pass. Make REST `/v1/search` `best_solution` carry the same fields MCP `recall` returns inline. Introduce ONE shared read-row builder in the Application layer (or a shared Presentation serializer) that both transports call; widen `BestSolutionResponse` to declare the full field set; add clean word-boundary preview truncation with a `content_truncated` flag and a full `content` field. No change to the frozen confidence math.

Clean Architecture discipline: keep business logic in `AgentbookService`; Presentation layers only serialize. Do NOT bump `confidence.py:__frozen_policy_version__` — every confidence-related change here only *surfaces* values the frozen math already computes.

## BDD Scenarios (target behavior)

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

- `backend/presentation/api/routes/search.py`
- `backend/presentation/api/schemas.py`
- `backend/application/service.py`
- `backend/presentation/mcp/tools.py`

## Interface contract (signatures only — no implementation bodies)

```python
# Presentation: widen the REST read model to the canonical read row
class BestSolutionResponse(BaseModel):  # backend/presentation/api/schemas.py
    solution_id: str
    confidence: float
    content: str
    content_preview: str
    content_truncated: bool
    steps: list[str] | None
    root_cause_pattern: str | None
    localization_cues: list[str]
    verification: list[dict]
    root_cause_class: str | None
    outcome_count: int
    confidence_inputs: dict | None
```

## Steps

1. Implement the change described above across the listed files, matching surrounding code style (Ruff, 88 cols, double quotes).
2. Keep both transports calling shared Application logic where applicable (no per-transport business logic).
3. Run the paired test file; confirm GREEN. Run `make fast` to confirm no regressions.

## Verification

```bash
uv run pytest backend/tests/unit/test_transport_read_parity.py -q   # expect PASS (Green)
make fast                                                   # no regressions
```
