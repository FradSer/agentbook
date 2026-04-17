# Task 010a: Sandbox circuit breaker trip and cooldown — Red

**depends-on**: 007b

## Description

Red tests for a 5-minute sliding-window circuit breaker that trips when ≥20% of sandbox invocations error (distinct from sandbox-fail verdicts). Tripped breaker forces `sandbox_available=False` for 5 minutes; the next invocation after cooldown runs as a probe — if it errors too, the breaker re-opens.

## Execution Context

**Task Number**: 010a of 41
**Phase**: Resilience — DoS gates
**Prerequisites**: Task 007b committed.

## BDD Scenario

```gherkin
Scenario: Circuit breaker trips at 20% error rate
  Given 100 sandbox runs have executed in the last 5 minutes
  And 21 of them raised container errors (not sandbox-fail verdicts)
  When the 101st run is requested
  Then sandbox_available is False for the next 5 minutes
  And every subsequent evaluate_improvement falls back to Bayesian confidence cleanly
  And a "sandbox_circuit_open" alert is surfaced on /health with opened_at timestamp

Scenario: Circuit breaker closes after cooldown
  Given the circuit breaker has been open for 5 minutes
  When the next sandbox invocation is requested
  Then sandbox_available is True again
  And a probing run executes with the normal timeout
  And the breaker re-opens only if the probe itself errors
```

**Spec Source**: `../2026-04-18-memory-layer-autoresearch-design/bdd-specs.md`

## Files to Modify/Create

- Create: `backend/tests/unit/test_sandbox_circuit_breaker.py`

## Steps

### Step 1: Controlled clock + fake sandbox
- Reuse the clock fixture from 009a. Use a `FlakySandbox` whose error rate is test-controlled.

### Step 2: Trip tests
- `test_breaker_trips_at_20_percent_error_rate` — 79 successful runs and 21 container errors in 5 minutes; assert the 101st call reports `sandbox_available == False` and falls back to Bayesian with no sandbox spawn. Assert `/health` metrics expose `sandbox_circuit_open.opened_at == now`.
- `test_breaker_does_not_trip_on_sandbox_fail_verdicts` — 79 pass, 21 `success=False` (sandbox-fail, NOT container error); breaker must NOT trip.

### Step 3: Cooldown tests
- `test_breaker_closes_after_5_minutes` — breaker trips at T=0; advance clock to T=5min; next call enters probing mode and runs; breaker state returns to closed on success.
- `test_breaker_reopens_on_probe_failure` — breaker trips at T=0; advance to T=5min; probe errors; breaker re-opens for another 5 minutes.

### Step 4: Confirm Red
- All four tests fail.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_sandbox_circuit_breaker.py -v
```

## Success Criteria

- Four failing tests.
- Clear distinction between "container error" (trips the breaker) and "sandbox_score=0 verdict" (does not trip).
