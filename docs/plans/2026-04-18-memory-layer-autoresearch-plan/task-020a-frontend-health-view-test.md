# Task 020a: Frontend /health view — Red

**depends-on**: 019b

## Description

Red tests for the `/health` page. Read-only operator surface. Shows sandbox pass rate (24h), inflated-confidence alerts (24h), circuit-breaker state, and counters. Asserts no write surfaces (no forms, no buttons that POST).

## Execution Context

**Task Number**: 020a of 41
**Phase**: Frontend reorg
**Prerequisites**: Task 019b committed.

## BDD Scenario

```gherkin
Scenario: /health shows aggregate sandbox + cluster metrics
  Given the last 24h contains 120 sandbox runs and 4 single-identity cluster alerts
  When /health renders
  Then "Sandbox pass rate (24h)" shows the computed percentage
  And "Inflated-confidence alerts (24h): 4" is visible
  And no form elements or write buttons are rendered
```

**Spec Source**: `../2026-04-18-memory-layer-autoresearch-design/bdd-specs.md`

## Files to Modify/Create

- Create: `frontend/tests/health-view.test.tsx`

## Steps

### Step 1: Tests
- Mock `fetch("/v1/health-metrics")` with a fixed response: `sandbox_pass_rate_24h: 0.75`, `single_identity_cluster_count_24h: 4`, `circuit_breaker: {state: "closed"}`.
- `test_health_page_renders_pass_rate` — `getByText(/Sandbox pass rate \(24h\)/i)` and `getByText(/75%/)` both present.
- `test_health_page_renders_cluster_alerts` — `getByText(/Inflated-confidence alerts \(24h\): 4/)`.
- `test_health_page_no_write_surfaces` — `queryByRole("button")` returns null for any button containing POST/delete semantics; `queryByRole("form")` returns null.
- `test_health_page_renders_circuit_state_open` — mock response with `circuit_breaker.state = "open"`; assert a coral pill labelled "Sandbox circuit OPEN" renders.

### Step 2: Confirm Red
- All four tests fail.

## Verification Commands

```bash
cd frontend && pnpm test tests/health-view.test.tsx
```

## Success Criteria

- Four failing tests.
- No-write-surface assertion is stricter than just "no form" — also excludes any button with a mutating `fetch` inside its handler (this can be enforced by ensuring the only fetch in the page is a GET).
