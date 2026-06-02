# Task 006 (recall-latency) — Impl (Green)

**type:** impl
**theme:** P0-C
**closes:** PR-9, PR-10
**depends-on:** [006-recall-latency-test]

## Goal

Make the Red tests from 006-recall-latency-test pass. Bound embedding I/O on the request path: pass a tight per-call client timeout to the Voyage client and cap the live-query retry budget so fallback to keyword is sub-second (keep the full retry only on the offline `embed_documents` backfill path). Ensure a recall miss is the cheapest path. Scope note: the larger async/deferred embed-on-write (PR-10 full) is the follow-on within this task's impl description; the bounded-timeout fix alone removes the catastrophic blocking case.

Clean Architecture discipline: keep business logic in `AgentbookService`; Presentation layers only serialize. Do NOT bump `confidence.py:__frozen_policy_version__` — every confidence-related change here only *surfaces* values the frozen math already computes.

## BDD Scenarios (target behavior)

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

- `backend/infrastructure/embeddings/voyage.py`
- `backend/application/service.py`

## Interface contract (signatures only — no implementation bodies)

```python
# Infrastructure: bounded client + capped live-path retry
class VoyageEmbeddingProvider:  # backend/infrastructure/embeddings/voyage.py
    def embed(self, text: str, *, input_type: str = 'query') -> list[float]: ...  # tight timeout, fast keyword fallback
_LIVE_RETRY_DELAYS_SECONDS = ()  # no blocking sleeps on the query path
```

## Steps

1. Implement the change described above across the listed files, matching surrounding code style (Ruff, 88 cols, double quotes).
2. Keep both transports calling shared Application logic where applicable (no per-transport business logic).
3. Run the paired test file; confirm GREEN. Run `make fast` to confirm no regressions.

## Verification

```bash
uv run pytest backend/tests/unit/test_recall_latency.py -q   # expect PASS (Green)
make fast                                                   # no regressions
```
