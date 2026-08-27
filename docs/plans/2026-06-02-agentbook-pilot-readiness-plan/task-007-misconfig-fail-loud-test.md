# Task 007 (misconfig-fail-loud) — Test (Red, historical)

**type:** test
**theme:** P0-C
**closes:** PR-11, misconfig
**depends-on:** [001]

## Goal

Write the failing (Red) BDD tests for the **Misconfiguration fails loud at boot** behavior. These tests encode the target contract and MUST fail against current `main` before the paired impl task (007-misconfig-fail-loud-impl) makes them pass.

## BDD Scenarios (source of truth)

```gherkin
Feature: Misconfiguration fails loud at boot

  The former embedding-provider cutover used a 1024-dimensional column beside
  a legacy 1536-dimensional column. This historical scenario records the
  failure mode that the current Workers AI-only runtime removes.

  Scenario: Former mismatched provider config refused to boot
    Given a legacy provider key and a 1536-dimensional column were configured
    When create_app() ran validate_production_settings()
    Then boot was refused with a surfaced dimension mismatch error

  Scenario: Provider field reflects the per-query mechanism, not boot config
    Given the service has fallen back to a keyword scan for a query
    When the response is built
    Then embedding_provider reflects the actual mechanism (e.g. "keyword" or null), not "voyage"
    And it agrees with search_mode "in_memory_scan" / "no_match"

  Scenario: Current Workers AI config boots cleanly
    Given Cloudflare Workers AI and its 1024-dimensional column are configured
    When create_app() runs
    Then boot succeeds

---
```

## Files

- `backend/tests/features/misconfig-fail-loud.feature` — the Gherkin above, verbatim.
- `backend/tests/unit/test_misconfig_fail_loud.py` — step implementations / assertions. Isolate external dependencies (DB, Voyage, network) with in-memory repos and test doubles per `backend/tests/conftest.py` conventions; use the `enable_limiter` fixture only where a scenario asserts rate-limit behavior.

## Steps

1. Copy the scenarios above into `misconfig-fail-loud.feature`.
2. Implement step defs / test functions asserting the target contract (NOT current behavior). For cross-transport parity scenarios, assert REST and MCP payloads field-by-field via a shared helper.
3. Run the tests; confirm they FAIL (Red) for the documented reason (current behavior diverges).

## Verification

```bash
uv run pytest backend/tests/unit/test_misconfig_fail_loud.py -q   # expect FAIL (Red) before impl
```
