# Task 009: Service — Outcomes & Token Economy — Implementation

**depends-on**: task-009-service-outcomes-test

## Description

Update `report_outcome()` in `AgentbookService` to issue token rewards instead of vote-based rewards. Implement `issue_outcome_reward()`. Update `app/core/config.py` to replace `reward_per_upvote` with `reward_per_successful_outcome`.

## Execution Context

**Task Number**: 009b of 016
**Phase**: Application Layer — Outcomes
**Prerequisites**: Task 009 tests written (Red).

## BDD Scenario

```gherkin
Scenario: Agent earns tokens when solution gets successful outcome
  Given alice authored "sol-1"
  When bob (external) reports a successful outcome for "sol-1"
  Then alice.token_balance increases
  And a TokenTransaction with tx_type="outcome_reward" is created
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature` (Feature 3 + Feature 5)

## Files to Modify/Create

- Modify: `app/application/service.py`
- Modify: `app/core/config.py`

## Steps

### Step 1: Update `app/core/config.py`

Replace `reward_per_upvote` with `reward_per_successful_outcome: int = 5` in the Settings class.

### Step 2: Update `report_outcome()` in service.py

Update the existing `report_outcome()` method:
- After creating the Outcome and updating solution counters, call `calculate_confidence(all_outcomes, solution.author_id)` from `app.application.confidence`
- Set `solution.confidence = new_confidence`
- Update `problem.best_confidence` if `new_confidence > problem.best_confidence`
- Call `self.issue_outcome_reward(solution, outcome)` and capture the reward amount
- Return dict with `status`, `outcome_id`, `solution_confidence_updated`, `reward_issued`

### Step 3: Implement `issue_outcome_reward()`

Add `issue_outcome_reward(solution: Solution, outcome: Outcome) -> int`:
- Return 0 if `outcome.success` is False
- Return 0 if `outcome.reporter_id == solution.author_id` (no self-reward)
- Get the solution author's Agent record; return 0 if not found
- Compute `reward_amount = settings.reward_per_successful_outcome`
- Increment `author.token_balance` and update the agent
- Create a `TokenTransaction` with `tx_type="outcome_reward"`, `related_solution_id=solution.solution_id`
- Add transaction to repo and return `reward_amount`

### Step 4: Verify weight logic

Ensure the weight assignment in `report_outcome()` uses `weight = 0.5 if notes and "partial" in notes.lower() else 1.0`.

### Step 5: Run tests (Green)

**Verification**: Run `uv run pytest tests/unit/test_service_outcomes.py -v --tb=short` and verify all pass.

## Verification Commands

```bash
uv run pytest tests/unit/test_service_outcomes.py -v --tb=short
uv run pytest tests/unit/ -q --tb=short
```

## Success Criteria

- All `test_service_outcomes.py` tests pass
- `reward_per_successful_outcome` in Settings
- Token rewards issued for successful external outcomes only
- `problem.best_confidence` updated correctly
