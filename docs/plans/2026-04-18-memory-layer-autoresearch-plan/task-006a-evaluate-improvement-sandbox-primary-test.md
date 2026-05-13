# Task 006a: evaluate_improvement sandbox-primary branch — Red

**depends-on**: 002b

## Description

Red tests for the new top-level sandbox-primary dispatch inside `evaluate_improvement`. Five scenarios exercise the guard: sandbox pass flips a lower Bayesian score; sandbox unavailable falls through cleanly; `error_signature=None` never invokes the sandbox; sandbox failure rejects regardless of `evaluator_score`; a sandbox tie falls back to the simplicity rule and returns `"sandbox_tied_simplification"`.

## Execution Context

**Task Number**: 006a of 41
**Phase**: Core — Sandbox primary
**Prerequisites**: Task 002b committed.

## BDD Scenario

```gherkin
Scenario: Sandbox pass flips acceptance despite lower Bayesian confidence
  Given a problem with error_signature "ImportError: cannot import name 'X'"
  And an existing solution with confidence 0.72
  And a proposed solution with confidence 0.55
  When the sandbox reproduces the error, existing fails to fix it, proposed fixes it
  Then the proposed solution is accepted with reason "sandbox_verified_pass"
  And exactly one Outcome is persisted with kind="verified", reporter_id=SANDBOX_AGENT_ID, success=True
  And the existing solution is marked superseded

Scenario: Sandbox unavailable falls back to Bayesian confidence
  Given a problem with error_signature "ConnectionRefusedError: port 5432"
  And the configured SandboxProvider raises SandboxUnavailable at call time
  And the proposed solution has confidence 0.80 and the existing 0.60
  When evaluate_improvement is called
  Then sandbox_score is None
  And the decision falls through to the legacy Bayesian branch
  And the proposed solution is accepted with reason "confidence_improved"

Scenario: No error_signature never invokes the sandbox
  Given a problem with error_signature = None
  And two candidate solutions with arbitrary confidences
  When evaluate_improvement is called
  Then the sandbox is NOT invoked
  And the decision uses the legacy Bayesian path only

Scenario: Sandbox failure on proposed rejects regardless of evaluator_score
  Given the LLM evaluator returned evaluator_score 0.92 for the proposed solution
  And the sandbox reproduces the error
  And the existing solution passes the sandbox
  And the proposed solution fails the sandbox
  When evaluate_improvement is called
  Then the proposed solution is rejected with reason "sandbox_verified_fail"
  And the evaluator_score is not consulted
  And one Outcome is persisted with kind="verified", success=False

Scenario: Both solutions pass the sandbox — simplicity tiebreaker
  Given both existing and proposed pass the sandbox
  And proposed.content length is 0.6 * existing.content length
  And proposed has the same number of steps as existing
  When evaluate_improvement is called
  Then the proposed solution is accepted with reason "sandbox_tied_simplification"
```

**Spec Source**: `../2026-04-18-memory-layer-autoresearch-design/bdd-specs.md`

## Files to Modify/Create

- Create: `backend/tests/unit/test_evaluate_improvement_sandbox_primary.py`

## Steps

### Step 1: Parameterised unit tests
- Build a fixture factory `build_solutions(existing_conf, proposed_conf, existing_len, proposed_len, ...)`.
- One test per scenario above. Tests call `evaluate_improvement(existing, proposed, sandbox_score=..., problem_has_error_signature=..., sandbox_available=...)` directly — NO Outcome persistence in this task (that belongs to 007).
- Assert the `(accepted, reason_code)` tuple matches the scenario expectation.

### Step 2: Ensure "no sandbox" path uses legacy tree
- The "no error_signature" test must monkeypatch the sandbox provider to raise on call — the guard must prevent the call. Assert the sandbox call count is zero.

### Step 3: Confirm Red
- All five tests must fail because the new branch does not yet exist. Today's `evaluate_improvement` has `sandbox_score` only in tier 3b.5 cold-start.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_evaluate_improvement_sandbox_primary.py -x -v
# Expected: 5 failed
```

## Success Criteria

- Five failing tests committed.
- Fixture factory reused where possible to keep each test tight.
- No change to `confidence.py` or `service.py` in this task.
