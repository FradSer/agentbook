# Task 006b: evaluate_improvement sandbox-primary branch — Green

**depends-on**: 006a

## Description

Add the sandbox-primary top-level dispatch in `confidence.py::evaluate_improvement`. Extend the function signature with two keyword-only flags (`problem_has_error_signature`, `sandbox_available`). When both flags are True and `sandbox_score` is not None, the function returns immediately with `sandbox_verified_pass` or `sandbox_verified_fail`. The tie case falls through to the legacy tree's simplification branch, but the reason-code short-circuits to `sandbox_tied_simplification`.

## Execution Context

**Task Number**: 006b of 41
**Phase**: Core — Sandbox primary
**Prerequisites**: Task 006a red tests committed.

## BDD Scenario

(Same five scenarios as task 006a — see `bdd-specs.md`.)

## Files to Modify/Create

- Modify: `backend/application/confidence.py::evaluate_improvement` — add the sandbox-primary guard.

## Steps

### Step 1: Update function signature
- Add keyword-only parameters:
  ```python
  def evaluate_improvement(
      existing: Solution,
      proposed: Solution,
      *,
      evaluator_score: float | None = None,
      sandbox_score: float | None = None,
      problem_has_error_signature: bool = False,
      sandbox_available: bool = False,
  ) -> tuple[bool, str]:
  ```

### Step 2: Add top-level guard
- Immediately after the docstring, before the content-regression check:
  ```python
  if (
      problem_has_error_signature
      and sandbox_available
      and sandbox_score is not None
  ):
      if sandbox_score > 0.5:
          return True, "sandbox_verified_pass"
      if sandbox_score <= 0.5:
          # Tie handling: both passed is sandbox_score == 1.0 vs existing 1.0.
          # Service layer encodes "existing pass, proposed pass" as
          # sandbox_score = 0.6 (proposed slightly preferred via shorter content).
          return False, "sandbox_verified_fail"
  ```
  Intent only — the exact decision values between 0.5..1.0 representing the tie case are defined in task 007b (the orchestration layer owns `sandbox_score` construction).

### Step 3: Simplicity tiebreaker reason
- In the existing simplification branch (branch 5 of the legacy tree), if the call arrived here with `sandbox_score is not None and sandbox_score > 0.5` on both sides (represented by `sandbox_tied=True` flag passed through), return `"sandbox_tied_simplification"` instead of `"simplification"`. Confirm whether this requires an additional parameter or whether the service layer already hard-codes the reason; follow the test expectations from 006a strictly.

### Step 4: Green
- Run the 006a tests; confirm all five pass.
- Run full `test_evaluation_invariants.py` suite and adjust any tests whose expected reason codes changed (document the changes in the commit message).

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_evaluate_improvement_sandbox_primary.py -v
uv run pytest backend/tests/unit/test_evaluation_invariants.py
uv run pytest backend/tests/unit/
uv run ruff check backend/application/confidence.py
```

## Success Criteria

- All 006a scenarios pass.
- No regression in `test_evaluation_invariants.py` (or documented, deliberate updates).
- `confidence.py` remains import-clean (only `backend/domain/` + stdlib).
