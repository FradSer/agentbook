# Task 006 — Implement: Confidence Scoring Engine

**Type:** Green (implementation)
**Depends-on:** task-005
**BDD refs:** Feature 3 Scenario "Agent reports solution worked", Feature 3 Scenario "Multiple outcome reports aggregate correctly"

## Goal

Implement `calculate_confidence()` in a new file `app/domain/scoring_v2.py`. Pure function, no external dependencies.

## What to implement

### `calculate_confidence(outcomes, author_id, initial_confidence=0.3) -> float`

Algorithm:
1. If no outcomes: return `initial_confidence`
2. For each outcome, compute its weight:
   - `base_weight = 0.5` if `outcome.reporter_id == author_id` else `1.0`
   - `recency_factor = exp(-days_elapsed / 90.0)` where `days_elapsed = (now - outcome.created_at).days`
   - `env_factor` = derived from `outcome.weight` field set at write time (1.0, 0.7, or 0.3)
   - `final_weight = base_weight * recency_factor * env_factor`
3. Compute `success_value`:
   - `outcome.success = True` → `1.0`
   - `outcome.success = False` → `0.0`
   - `outcome.notes` containing "partial" marker → `0.5` (convention: service layer sets `weight=0.5` for partial)
4. Apply reporter diversity penalty:
   - Group outcomes by `reporter_id`
   - `effective_count = len(unique_reporters) * log2(len(all_outcomes) + 1)`
   - If `effective_count < len(all_outcomes)`, scale weights proportionally
5. `confidence = sum(success_value * weight) / sum(weight)` clamped to `[0.0, 1.0]`

### `calculate_environment_confidence(outcomes, target_environment) -> float | None`

Returns environment-specific confidence (only outcomes from matching environment). Returns `None` if fewer than 2 environment-specific outcomes exist.

## Files to create

- `app/domain/scoring_v2.py`

## Verification

```bash
uv run pytest tests/unit/test_confidence_scoring.py -v
```

All tests from task-005 must pass (green).
