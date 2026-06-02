# Task 009 (rejection-signaling-parity) — Test (Red)

**type:** test
**theme:** P0-A
**closes:** PR-3, acceptance-window
**depends-on:** [001]

## Goal

Write the failing (Red) BDD tests for the **Transport parity for rejection signaling on the improve write contract** behavior. These tests encode the target contract and MUST fail against current `main` before the paired impl task (009-rejection-signaling-parity-impl) makes them pass.

## BDD Scenarios (source of truth)

```gherkin
Feature: Transport parity for rejection signaling on the improve write contract

  A gated/rejected improvement must signal failure identically across
  transports, so a client keying off HTTP status or result.isError reaches the
  same conclusion on REST and MCP. Today the frozen gate's rejection arrives as
  REST 409 + error envelope but MCP 200 + isError:false (the rejection buried
  in the payload), so an MCP client believes a gated improvement succeeded.
  The gate decision (FROZEN math, confidence.py:149) is never altered — only
  the way its rejection is signalled is unified across transports.

  Scenario: A frozen-gate rejection is signalled identically on REST and MCP
    Given an improve submission the frozen gate rejects as "content_bloat"
    When an agent submits it over REST POST /v1/solutions/{id}/improve
    And an agent submits the same improvement over MCP remember improve-mode
    Then both transports signal rejection through the single authoritative field (non-2xx / result.isError true)
    And both carry the same reason "content_bloat" and the same next_action
    And a client keying off HTTP status or isError detects the rejection identically on both transports

  Scenario: An accepted improvement is signalled identically on REST and MCP
    Given an improve submission that lands in the cold-start acceptance window
    When an agent submits it over REST and over MCP
    Then both transports signal acceptance (2xx / result.isError false) with candidate_status "candidate"
    And neither transport reports success for a submission the other reports as rejected

---
```

## Files

- `backend/tests/features/rejection-signaling-parity.feature` — the Gherkin above, verbatim.
- `backend/tests/unit/test_rejection_signaling_parity.py` — step implementations / assertions. Isolate external dependencies (DB, Voyage, network) with in-memory repos and test doubles per `backend/tests/conftest.py` conventions; use the `enable_limiter` fixture only where a scenario asserts rate-limit behavior.

## Steps

1. Copy the scenarios above into `rejection-signaling-parity.feature`.
2. Implement step defs / test functions asserting the target contract (NOT current behavior). For cross-transport parity scenarios, assert REST and MCP payloads field-by-field via a shared helper.
3. Run the tests; confirm they FAIL (Red) for the documented reason (current behavior diverges).

## Verification

```bash
uv run pytest backend/tests/unit/test_rejection_signaling_parity.py -q   # expect FAIL (Red) before impl
```
