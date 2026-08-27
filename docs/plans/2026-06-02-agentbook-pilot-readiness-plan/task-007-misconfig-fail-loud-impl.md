# Task 007 (misconfig-fail-loud) — Impl (Green, historical)

**type:** impl
**theme:** P0-C
**closes:** PR-11, misconfig
**depends-on:** [007-misconfig-fail-loud-test]

## Goal

This historical task documented provider cutover safeguards. The current Workers AI-only runtime validates its embedding dimension at boot and reports the mechanism that actually served each query.

Clean Architecture discipline: keep business logic in `AgentbookService`; Presentation layers only serialize. Do NOT bump `confidence.py:__frozen_policy_version__` — every confidence-related change here only *surfaces* values the frozen math already computes.

## BDD Scenarios (target behavior)

```gherkin
Feature: Misconfiguration fails loud at boot

  The former embedding-provider cutover used a 1024-dimensional column beside
  a legacy 1536-dimensional column. The current Workers AI-only runtime uses
  the 1024-dimensional column exclusively.

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
