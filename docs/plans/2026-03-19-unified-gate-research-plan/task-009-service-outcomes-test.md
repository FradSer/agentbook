# Task 009: Service — Outcomes & Token Economy — Test

**depends-on**: task-006-service-problem-crud-impl

## Description

Write unit tests for `report_outcome()` and `issue_outcome_reward()`. Tests cover the Bayesian confidence update, rate limiting (10 per hour), partial failure weighting, self-report exclusion from confidence, the external corroboration requirement, and the outcome-based token reward system.

## Execution Context

**Task Number**: 009a of 016
**Phase**: Application Layer — Outcomes
**Prerequisites**: `create_problem`/`create_solution` implemented (Task 006). This task is independent of Tasks 007 and 008.

## BDD Scenario

```gherkin
Scenario: External agent reports successful outcome — confidence increases
  Given solution "sol-1" with author_verified=false and no prior outcomes
  When bob (external) reports a successful outcome for "sol-1"
  Then an Outcome record is created with success=true, weight=1.0
  And solution.outcome_count increases to 1
  And solution.success_count increases to 1
  And solution.confidence is above 0.3 baseline

Scenario: Rate limiting — max 10 outcome reports per hour per agent
  Given bob has reported 10 outcomes in the last hour
  When bob attempts to report another outcome
  Then RateLimitError is raised with message "Rate limit exceeded: max 10 outcomes per hour"

Scenario: Partial failure outcomes weighted at 0.5
  Given bob reports an outcome with notes "partial failure — worked for Alpine but not Ubuntu"
  Then the outcome is created with weight=0.5

Scenario: Self-reported outcomes do not raise confidence above baseline
  Given alice is the author of "sol-1" (author_verified=false)
  When alice reports 5 successful outcomes for her own "sol-1"
  Then confidence remains at 0.3 (zero external reporters)

Scenario: Agent earns tokens when solution gets successful outcome
  Given alice authored "sol-1" and has token_balance=100
  When bob reports a successful outcome for "sol-1"
  Then alice.token_balance increases by reward_per_successful_outcome
  And a TokenTransaction with tx_type="outcome_reward" is created for alice

Scenario: No tokens for failed outcomes
  Given alice authored "sol-1"
  When bob reports a failed outcome
  Then alice.token_balance does not change

Scenario: No self-reward for own outcome reports
  Given alice authored "sol-1"
  When alice reports a successful outcome for her own "sol-1"
  Then alice.token_balance does not change

Scenario: Problem best_confidence tracks highest solution confidence
  Given problem "prob-1" has best_confidence=0.3
  When an outcome raises "sol-1" confidence to 0.7
  Then problem.best_confidence is updated to 0.7
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature` (Feature 3 + Feature 5)

## Files to Modify/Create

- Create: `tests/unit/test_service_outcomes.py`

## Steps

### Step 1: Write tests (Red)

In `tests/unit/test_service_outcomes.py`, register agents, create problems/solutions using the service, then:
1. Call `service.report_outcome(reporter_id, solution_id, success=True)` and verify confidence increases
2. Verify rate limit at 10 reports per hour (monkeypatch time or add 10 outcomes manually)
3. Verify `weight=0.5` when notes contain "partial"
4. Verify self-reports don't move confidence above 0.3 baseline
5. Verify single external report moves confidence above 0.3
6. Verify token reward issued on successful external outcome
7. Verify no reward on failed outcome
8. Verify no self-reward when reporter == solution author
9. Verify `problem.best_confidence` updated when solution confidence increases
10. Verify `result["reward_issued"]` in the return dict

Also include the recency and combined-reporter scenarios:
10. Verify rate limit resets: create an outcome reporter who hit the limit, monkeypatch the time so `since` = now - 61 minutes, verify a new report succeeds
11. Verify combined self + external reports: alice reports 2 successes (self), bob reports 1 success (external) → confidence above baseline (external reporter unlocks movement, alice's reports contribute at 0.5 base_weight)
12. Verify recency decay is applied: create 2 outcomes for the same solution, one with `created_at = now - 1 day` (high weight) and one with `created_at = now - 180 days` (low weight), assert recent outcome dominates confidence calculation (this tests `calculate_confidence` integration)

**Verification**: Run `uv run pytest tests/unit/test_service_outcomes.py --tb=short` and verify failures.

## Verification Commands

```bash
uv run pytest tests/unit/test_service_outcomes.py -v --tb=short
```

## Success Criteria

- All tests fail (Red phase complete)
- Failures confirm missing `report_outcome` behavior or wrong confidence/token logic
