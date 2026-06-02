# Task 006 (recall-latency) — Test (Red)

**type:** test
**theme:** P0-C
**closes:** PR-9, PR-10
**depends-on:** [001]

## Goal

Write the failing (Red) BDD tests for the **Bounded recall latency on the read contract** behavior. These tests encode the target contract and MUST fail against current `main` before the paired impl task (006-recall-latency-impl) makes them pass.

## BDD Scenarios (source of truth)

```gherkin
Feature: Bounded recall latency on the read contract

  Recall is positioned as an agent's near-free FIRST move on hitting an error,
  cheaper than local reasoning. A recall on a novel query must return within a
  bounded time even when the embedding provider is slow or misconfigured: the
  embedding call has a tight client timeout and degrades fast to keyword
  fallback, with no unbounded blocking retry storm on the request path.

  Scenario: Novel-query recall returns within the latency budget on a healthy provider
    Given the embedding provider is healthy
    When an agent issues a recall for a never-seen query
    Then the response returns within the recall latency budget (sub-second target)

  Scenario: Slow embedding provider degrades fast, not after a retry storm
    Given the embedding provider is configured but unresponsive
    When an agent issues a recall for a novel query
    Then the embedding call aborts at a bounded client timeout
    And the service degrades to keyword fallback within the latency budget
    And it does NOT perform synchronous 1s + 2s + 4s blocking retry sleeps on the request path

  Scenario: A miss is cheap
    Given a query that matches nothing
    When an agent issues the recall
    Then the response returns within the latency budget
    And carries no_good_match true with search_mode "no_match"

  Scenario: Embed-on-write does not dominate contribute latency
    Given the embedding provider is slow
    When an authenticated agent POSTs /v1/problems
    Then the write returns without blocking on a multi-second synchronous embed
    And the embedding is computed asynchronously or deferred

---
```

## Files

- `backend/tests/features/recall-latency.feature` — the Gherkin above, verbatim.
- `backend/tests/unit/test_recall_latency.py` — step implementations / assertions. Isolate external dependencies (DB, Voyage, network) with in-memory repos and test doubles per `backend/tests/conftest.py` conventions; use the `enable_limiter` fixture only where a scenario asserts rate-limit behavior.

## Steps

1. Copy the scenarios above into `recall-latency.feature`.
2. Implement step defs / test functions asserting the target contract (NOT current behavior). For cross-transport parity scenarios, assert REST and MCP payloads field-by-field via a shared helper.
3. Run the tests; confirm they FAIL (Red) for the documented reason (current behavior diverges).

## Verification

```bash
uv run pytest backend/tests/unit/test_recall_latency.py -q   # expect FAIL (Red) before impl
```
