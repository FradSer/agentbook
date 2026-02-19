# Task 013 — Test: AgentbookServiceV2.report_outcome()

**Type:** Red (test first)
**Depends-on:** task-004, task-006
**BDD refs:** Feature 3 all scenarios (Outcome Reporting)

## Goal

Write failing unit tests for the `report_outcome()` method of `AgentbookServiceV2`.

## What to test

### Success report increases confidence
- Given Solution S100, `author_id=agent-gpt-4`, 10 prior outcomes (7 success, 3 failure), confidence 0.70
- When `report_outcome(reporter_id=agent-claude-7, solution_id=S100, success=True, environment={...})` called
- Then outcome stored, `S100.confidence` recalculated to ≈ 0.727, response includes `solution_confidence_updated`

### Failure report decreases confidence
- Given same S100 baseline
- When `report_outcome(reporter_id=agent-claude-7, solution_id=S100, success=False, environment={"python": "3.13"})` called
- Then `S100.confidence` recalculated to ≈ 0.636

### Partial success
- When `report_outcome` called with `success=False` and notes containing partial marker (e.g., "partial")
- Then outcome weight set to 0.5 (half success), confidence updates between full success and full failure

### Environment-specific confidence
- Given 2 success outcomes from Python 3.12 and 1 failure from Python 3.13
- When `calculate_environment_confidence(outcomes, {"python": "3.12"})` called
- Then returns confidence ≈ 1.0 for Python 3.12
- When called with `{"python": "3.13"}` → returns ≈ 0.0

### Anti-gaming: self-report rejected (author === reporter)
- Given agent-gpt-4 authored S100
- When `report_outcome(reporter_id=agent-gpt-4, solution_id=S100, ...)` called
- Then raises `DuplicateVoteError` or custom `SelfReportError` with message "self_reporting_not_allowed"
- And S100 confidence unchanged

### Rate limiting
- Given agent-claude-7 has already submitted 10 outcomes in the last hour
- When 11th `report_outcome` called
- Then raises `RateLimitError` (or returns error status)

### Solution not found
- When `report_outcome` called with non-existent `solution_id`
- Then raises `NotFoundError`

## Files to create

- `tests/unit/test_service_report_outcome.py`

## Verification

```bash
uv run pytest tests/unit/test_service_report_outcome.py -v
```

Tests must fail (red) before implementation.
