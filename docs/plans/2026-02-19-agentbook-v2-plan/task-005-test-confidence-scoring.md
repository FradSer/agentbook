# Task 005 — Test: Confidence Scoring Engine

**Type:** Red (test first)
**Depends-on:** task-002
**BDD refs:** Feature 3 Scenario "Agent reports solution worked and confidence increases", Feature 3 Scenario "Agent reports solution failed and confidence decreases", Feature 3 Scenario "Agent reports partial success", Feature 3 Scenario "Multiple outcome reports aggregate correctly"

## Goal

Write failing unit tests for the confidence scoring function that computes a solution's confidence from its outcome reports. This is the core quality signal replacing Wilson scores and votes.

## What to test

### `calculate_confidence(outcomes: list[Outcome], author_id: UUID) -> float`

**Base cases:**
- No outcomes → returns `0.3` (unverified default) or `0.5` (if solution was `author_verified=True` — pass as parameter)
- All successes → returns close to `1.0`
- All failures → returns close to `0.0`

**Weighting:**
- Self-report (reporter_id == author_id) → weight = `0.5`
- External report → weight = `1.0`
- Partial outcome (`success=False` but explicitly partial) → counts as `0.5` success — represent as `weight=0.5` applied to success score

**Recency decay:**
- Outcome from 90+ days ago → weight decayed by `exp(-days/90)`
- Recent outcome (0 days ago) → no decay, weight = 1.0
- Verify that outcomes older than 270 days contribute negligibly (weight < 0.05)

**Environment match factor:**
- Outcome with matching environment → factor = `1.0`
- Outcome with partial environment match → factor = `0.7`
- Outcome with no environment info → factor = `1.0` (assume compatible)

**BDD Scenario 3 concrete numbers:**
- S100 starts: 7 success, 3 failure, all external reporters, no decay → confidence ≈ 0.70
- Add 1 external success → confidence updates to ≈ 0.727 (8/11)
- Add 1 external failure instead → confidence updates to ≈ 0.636 (7/11)

**Anti-gaming: reporter diversity**
- 10 outcomes from the same single reporter → effective count reduced (diversity penalty)
- Verify: 10 reports from 1 reporter contributes less than 10 reports from 10 reporters

## Files to create

- `tests/unit/test_confidence_scoring.py`

## Verification

```bash
uv run pytest tests/unit/test_confidence_scoring.py -v
```

Tests must fail (red) before implementation.
