# Task 007 (misconfig-fail-loud) — Impl (Green)

**type:** impl
**theme:** P0-C
**closes:** PR-11, misconfig
**depends-on:** [007-misconfig-fail-loud-test]

## Goal

Make the Red tests from 007-misconfig-fail-loud-test pass. Emit a loud WARN at boot in every mode (not only production) when `voyage_api_key` is set with `embedding_version == 'v1'` (1536 vs 1024 mismatch), keeping the hard raise for production. Make per-query provider fields (`embedding_provider`/`rerank_provider`) reflect the mechanism that actually ranked (keyword/null) rather than the boot-configured name, or add a `dense_used: bool`.

Clean Architecture discipline: keep business logic in `AgentbookService`; Presentation layers only serialize. Do NOT bump `confidence.py:__frozen_policy_version__` — every confidence-related change here only *surfaces* values the frozen math already computes.

## BDD Scenarios (target behavior)

```gherkin
Feature: Misconfiguration fails loud at boot

  Voyage outputs 1024-dim vectors; the legacy column is vector(1536).
  EMBEDDING_VERSION=v1 together with a Voyage key is a dimension mismatch that
  would silently degrade every recall to keyword search while the response
  still advertises embedding_provider "voyage". This must fail loud, not
  silently degrade.

  Scenario: v1 plus a Voyage key refuses to boot
    Given EMBEDDING_VERSION is "v1"
    And VOYAGE_API_KEY is set
    When create_app() runs validate_production_settings()
    Then boot is refused with a surfaced error naming the dimension mismatch (1024 vs 1536)

  Scenario: Provider field reflects the per-query mechanism, not boot config
    Given the service has fallen back to a keyword scan for a query
    When the response is built
    Then embedding_provider reflects the actual mechanism (e.g. "keyword" or null), not "voyage"
    And it agrees with search_mode "in_memory_scan" / "no_match"

  Scenario: A consistent v2 / Voyage config boots cleanly
    Given EMBEDDING_VERSION is "v2"
    And VOYAGE_API_KEY is set
    When create_app() runs
    Then boot succeeds

---
```

## Files

- `backend/core/config.py`
- `backend/main.py`
- `backend/application/service.py`

## Interface contract (signatures only — no implementation bodies)

```python
# Composition Root / Application: per-query honest provider reporting
# when search_mode in {in_memory_scan, keyword_fallback, no_match}: embedding_provider = 'keyword'
```

## Steps

1. Implement the change described above across the listed files, matching surrounding code style (Ruff, 88 cols, double quotes).
2. Keep both transports calling shared Application logic where applicable (no per-transport business logic).
3. Run the paired test file; confirm GREEN. Run `make fast` to confirm no regressions.

## Verification

```bash
uv run pytest backend/tests/unit/test_misconfig_fail_loud.py -q   # expect PASS (Green)
make fast                                                   # no regressions
```
