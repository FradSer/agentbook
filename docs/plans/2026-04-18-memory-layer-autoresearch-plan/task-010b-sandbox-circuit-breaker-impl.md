# Task 010b: Sandbox circuit breaker trip and cooldown — Green

**depends-on**: 010a

## Description

Implement `SandboxCircuitBreaker` tracking the last 5 minutes of `(timestamp, outcome)` pairs where outcome ∈ {`success`, `sandbox_fail`, `container_error`}. Breaker trips when `container_error / total >= 0.20` with `total >= 10`. Open state returns `SandboxUnavailable` immediately. After 5 minutes the next call probes; probe success closes the breaker, probe error re-opens it.

## Execution Context

**Task Number**: 010b of 41
**Phase**: Resilience — DoS gates
**Prerequisites**: Task 010a red tests committed.

## BDD Scenario

(Same as task 010a — see `bdd-specs.md`.)

## Files to Modify/Create

- Modify: `backend/core/sandbox_gates.py` — add `SandboxCircuitBreaker` class.
- Modify: `backend/application/service.py::improve_solution` sandbox branch — breaker check is the first gate.
- Modify: `backend/core/config.py` — add `sandbox_circuit_error_rate: float = 0.20`, `sandbox_circuit_cooldown_minutes: int = 5`, `sandbox_circuit_min_samples: int = 10`.

## Steps

### Step 1: SandboxCircuitBreaker
- Signature:
  ```python
  class SandboxCircuitBreaker:
      def should_allow(self, now: datetime) -> bool: ...
      def record(self, outcome: Literal["success", "sandbox_fail", "container_error"], now: datetime) -> None: ...
      @property
      def state(self) -> Literal["closed", "open", "probing"]: ...
      @property
      def opened_at(self) -> datetime | None: ...
  ```
- Internal state: deque of `(ts, outcome)` with a ring buffer or TTL-based eviction; `opened_at` persists while breaker is open or probing.

### Step 2: Service integration
- Before any budget/dedup/semaphore check, call `breaker.should_allow(now)`. If False, raise `SandboxUnavailable()` and let the existing fallback path handle Bayesian.
- After each sandbox call, call `breaker.record(outcome, now)` with `container_error` for exceptions other than `SandboxFail` verdicts.

### Step 3: Expose state for /health
- `AgentbookService.get_health_metrics()` (will be finalised in task 019b) returns `{"sandbox_circuit_open": bool, "opened_at": datetime | None}` directly from `self._breaker`.

### Step 4: Green
- Run 010a tests.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_sandbox_circuit_breaker.py -v
uv run ruff check backend/core/sandbox_gates.py
```

## Success Criteria

- All 010a scenarios pass.
- Breaker distinguishes `container_error` (trips) from `sandbox_fail` (does not trip).
- Probing re-opens cleanly on probe failure.
