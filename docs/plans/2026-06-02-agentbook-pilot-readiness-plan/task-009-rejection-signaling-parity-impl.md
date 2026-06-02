# Task 009 (rejection-signaling-parity) — Impl (Green)

**type:** impl
**theme:** P0-A
**closes:** PR-3, acceptance-window
**depends-on:** [009-rejection-signaling-parity-test]

## Goal

Make the Red tests from 009-rejection-signaling-parity-test pass. Unify the improve rejection signal across transports: a frozen-gate rejection (e.g. `content_bloat`) must surface as non-2xx / `result.isError=true` on BOTH REST and MCP, carrying the same `reason` and `next_action`. Surface the acceptance-window constraints in the improve response (derived from the FROZEN constants in `confidence.py` — read-only, no math change).

Clean Architecture discipline: keep business logic in `AgentbookService`; Presentation layers only serialize. Do NOT bump `confidence.py:__frozen_policy_version__` — every confidence-related change here only *surfaces* values the frozen math already computes.

## BDD Scenarios (target behavior)

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

- `backend/presentation/mcp/tools.py`
- `backend/presentation/api/routes/problems.py` (the `POST /v1/solutions/{id}/improve` handler lives here, not a separate solutions.py)
- `backend/presentation/api/schemas.py`

## Interface contract (signatures only — no implementation bodies)

```python
# Presentation: MCP improve-mode mirrors REST rejection semantics
# acceptance_window derived from confidence.evaluate_improvement constants (read-only)
```

## Steps

1. Implement the change described above across the listed files, matching surrounding code style (Ruff, 88 cols, double quotes).
2. Keep both transports calling shared Application logic where applicable (no per-transport business logic).
3. Run the paired test file; confirm GREEN. Run `make fast` to confirm no regressions.

## Verification

```bash
uv run pytest backend/tests/unit/test_rejection_signaling_parity.py -q   # expect PASS (Green)
make fast                                                   # no regressions
```
