# Task 014 — Implement: AgentbookServiceV2.report_outcome()

**Type:** Green (implementation)
**Depends-on:** task-013
**BDD refs:** Feature 3 all scenarios (Outcome Reporting)

## Goal

Add `report_outcome()` to `AgentbookServiceV2` and add `SelfReportError`, `RateLimitError` to `app/application/errors.py`.

## What to implement

### New error types in `app/application/errors.py`
- `SelfReportError(AgentbookError)` — raised when reporter_id matches solution author_id
- `RateLimitError(AgentbookError)` — raised when rate limit exceeded

### `report_outcome(reporter_id, solution_id, problem_id?, success, environment?, error_after?, time_saved_seconds?, notes?) -> dict`

**Algorithm:**
1. Fetch solution from `solutions.get(solution_id)` — raise `NotFoundError` if missing
2. Check `reporter_id == solution.author_id` → raise `SelfReportError`
3. Check rate limit: `outcomes.count_by_reporter(reporter_id, since=now-1h) >= 10` → raise `RateLimitError`
4. Compute outcome `weight`:
   - Base: `1.0` (external) or `0.5` (self — already blocked above, kept for future relaxation)
   - If environment provided and matches solution's known environment: `weight *= 1.0`; partial match: `weight *= 0.7`; no match: `weight *= 0.3`
   - If "partial" in `notes.lower()` (partial success): multiply success contribution by `0.5` (store as `weight = weight * 0.5` on the Outcome)
5. Create `Outcome` with computed `weight`, call `outcomes.add(outcome)`
6. Fetch all outcomes for solution via `outcomes.list_by_solution(solution_id)`
7. Recalculate `solution.confidence` using `calculate_confidence(all_outcomes, solution.author_id)`
8. Call `solutions.update(solution)`
9. Update `solution.author` agent's `reputation` (small increment for success, no change for failure)
10. Return `{"outcome_id": ..., "solution_confidence_updated": new_confidence, "reputation_delta": delta}`

## Files to modify

- `app/application/errors.py` — add `SelfReportError`, `RateLimitError`
- `app/application/service_v2.py` — add `report_outcome()` method

## Verification

```bash
uv run pytest tests/unit/test_service_report_outcome.py -v
```

All tests from task-013 must pass (green).
