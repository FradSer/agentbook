# Task 007a: AgentbookService sandbox orchestration and verified outcomes — Red

**depends-on**: 006b

## Description

Red tests for `AgentbookService.improve_solution` orchestrating the sandbox call, emitting exactly one verified `Outcome` per run, and handling `SandboxTimeout`/`SandboxUnavailable` gracefully (falling back to Bayesian). The "no separate SandboxResult table" invariant is verified by asserting that sandbox history is reconstructable by a single SQL filter on `outcomes`.

## Execution Context

**Task Number**: 007a of 41
**Phase**: Core — Sandbox orchestration
**Prerequisites**: Task 006b committed.

## BDD Scenario

```gherkin
Scenario: Sandbox timeout is NOT a failure
  Given the sandbox exceeds SANDBOX_TIMEOUT_SECONDS = 30
  When the sandbox harness raises SandboxTimeout
  Then the decision is recorded with sandbox_score = None
  And evaluation falls back to Bayesian confidence
  And a sandbox_timeout counter is incremented for the /health view
  And no verified Outcome is persisted (nothing was measured)

Scenario: Sandbox result persists as Outcome — no separate SandboxResult table
  Given a sandbox run completes with exit_code 0
  When the acceptance pipeline finishes
  Then no row is written to any "sandbox_result" or "sandbox_run" table
  And the sandbox history for the solution is reconstructable by
    SELECT * FROM outcomes WHERE solution_id = ? AND kind = "verified" ORDER BY created_at
```

**Spec Source**: `../2026-04-18-memory-layer-autoresearch-design/bdd-specs.md`

## Files to Modify/Create

- Create: `backend/tests/unit/test_service_sandbox_orchestration.py`

## Steps

### Step 1: Fake SandboxProvider
- Build a `FakeSandbox` with four modes: always-pass, always-fail, raise-timeout, raise-unavailable. Use pytest fixtures to parametrise.

### Step 2: Tests
- `test_sandbox_pass_emits_verified_outcome_success_true` — call `service.improve_solution(...)` on a problem with `error_signature`; assert one Outcome row exists with `kind="verified"`, `reporter_id=SANDBOX_AGENT_ID`, `success=True`.
- `test_sandbox_fail_emits_verified_outcome_success_false` — same, but `success=False`.
- `test_sandbox_timeout_does_not_emit_outcome` — fake raises `SandboxTimeout`; assert zero verified outcomes created, assert `service.get_health_counter("sandbox_timeout") == 1`.
- `test_sandbox_unavailable_does_not_emit_outcome` — fake raises `SandboxUnavailable`; assert zero verified outcomes created.
- `test_no_sandbox_result_table_exists` — inspect SQLAlchemy metadata; assert no table named `sandbox_result`, `sandbox_run`, or similar.
- `test_sandbox_history_reconstructable_via_outcome_filter` — after 3 sandbox runs, `SELECT * FROM outcomes WHERE solution_id=? AND kind='verified' ORDER BY created_at` returns 3 rows matching the expected successes/failures.

### Step 3: Confirm Red
- All six tests FAIL because today's `service.improve_solution` does not call the sandbox as a primary gate and does not emit verified outcomes.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_service_sandbox_orchestration.py -x -v
```

## Success Criteria

- Six failing tests.
- `FakeSandbox` fixture reusable by tasks 008-010.
- No production code modified in this task.
