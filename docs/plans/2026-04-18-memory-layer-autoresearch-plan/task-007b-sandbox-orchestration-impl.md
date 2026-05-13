# Task 007b: AgentbookService sandbox orchestration and verified outcomes — Green

**depends-on**: 007a

## Description

Implement the sandbox orchestration path in `AgentbookService.improve_solution`. Add `_emit_verified_outcome(solution, sandbox_result)` that persists exactly one verified outcome per sandbox invocation. Add a simple `_health_counters: dict[str, int]` and `_increment_health_counter(name)` used by task 019b. Handle `SandboxTimeout` and `SandboxUnavailable` as soft failures (no outcome persisted; counter bumped; evaluation falls back via `sandbox_score=None`).

## Execution Context

**Task Number**: 007b of 41
**Phase**: Core — Sandbox orchestration
**Prerequisites**: Task 007a red tests committed.

## BDD Scenario

(Same scenarios as task 007a — see `bdd-specs.md`.)

## Files to Modify/Create

- Modify: `backend/application/service.py::AgentbookService.improve_solution`.
- Modify: `backend/application/service.py::AgentbookService.__init__` — add `_health_counters: dict[str, int] = {}` attribute.
- Modify: `backend/domain/services.py::SandboxProvider` — add `SandboxTimeout` and `SandboxUnavailable` exception classes if not already defined.

## Steps

### Step 1: Sandbox exceptions
- Define `class SandboxTimeout(Exception)` and `class SandboxUnavailable(Exception)` in `backend/domain/services.py` alongside the `SandboxProvider` Protocol, if absent.

### Step 2: Orchestration path in improve_solution
Add at the top of `improve_solution`:
```python
problem = self.problems.get(solution_to_improve.problem_id)
sandbox_available = (
    self.sandbox is not None
    and not isinstance(self.sandbox, NoopSandbox)
)
sandbox_score: float | None = None

if problem.error_signature and sandbox_available:
    try:
        existing_result = self.sandbox.run(problem, existing_solution, timeout_s=30)
        proposed_result = self.sandbox.run(problem, proposed_solution, timeout_s=30)
        sandbox_score = _combine_sandbox_results(existing_result, proposed_result)
        self._emit_verified_outcome(existing_solution, existing_result)
        self._emit_verified_outcome(proposed_solution, proposed_result)
    except SandboxTimeout:
        self._increment_health_counter("sandbox_timeout")
        sandbox_score = None
    except SandboxUnavailable:
        sandbox_score = None

accepted, reason = evaluate_improvement(
    existing_solution,
    proposed_solution,
    evaluator_score=evaluator_score,
    sandbox_score=sandbox_score,
    problem_has_error_signature=bool(problem.error_signature),
    sandbox_available=sandbox_available,
)
```

Intent only — exact execution (executor-side) must thread these calls through the existing `improve_solution` flow without breaking current outcome ordering.

### Step 3: _emit_verified_outcome helper
- Private method: accepts `(Solution, SandboxResult)`. Builds an `Outcome(kind="verified", reporter_id=SANDBOX_AGENT_ID, success=result.success, environment=result.environment, notes=(result.stderr or result.stdout)[:500])` and calls `self.outcomes.add(outcome)`. Returns None.

### Step 4: _combine_sandbox_results helper
- Pure function: given two `SandboxResult` values (existing, proposed), produce `sandbox_score ∈ {0.0, 0.5, 0.6, 1.0}`:
  - both fail → 0.0
  - existing pass, proposed fail → 0.0
  - existing fail, proposed pass → 1.0
  - both pass → 0.6 (simplicity branch activates; evaluate_improvement treats as decisive pass with simplification check)
- Place helper in `service.py` (not `confidence.py`; this is orchestration, not policy). Document mapping in comment ONE short line max per CLAUDE.md.

### Step 5: Green
- Run the 007a tests + broader unit suite.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_service_sandbox_orchestration.py -v
uv run pytest backend/tests/unit/
uv run ruff check backend/application/service.py backend/domain/services.py
```

## Success Criteria

- All 007a scenarios pass.
- `_health_counters` dict observable via a new `get_health_counter` or similar read method (will be consumed in 019b).
- No duplicate writes per run; no new DB table.
