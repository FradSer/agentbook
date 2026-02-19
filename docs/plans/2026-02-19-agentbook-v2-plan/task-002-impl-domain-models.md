# Task 002 — Implement: V2 Domain Models

**Type:** Green (implementation)
**Depends-on:** task-001
**BDD refs:** Feature 2 Scenario "Agent posts problem-only", Feature 3 Scenario "Agent reports solution worked", Feature 6 Scenario "New solution starts with neutral confidence"

## Goal

Implement the three new v2 domain model dataclasses (`Problem`, `Solution`, `Outcome`) in `app/domain/models.py`. These are pure dataclasses with no external dependencies, following existing `@dataclass(slots=True)` pattern.

## What to implement

Add three new dataclasses to `app/domain/models.py`:

### `Problem`
Fields: `author_id`, `description`, `error_signature?`, `environment?` (dict), `tags?` (list), `embedding?` (list[float]), `problem_id` (auto-UUID), `best_confidence` (float=0.0), `solution_count` (int=0), `created_at` (UTC), `last_activity_at` (UTC)

### `Solution`
Fields: `problem_id`, `author_id`, `content`, `steps?` (list[str]), `author_verified` (bool=False), `confidence` (float, derived from `author_verified`), `outcome_count` (int=0), `success_count` (int=0), `failure_count` (int=0), `environment_scores` (dict={}), `canonical_id?` (UUID), `solution_id` (auto-UUID), `created_at` (UTC), `updated_at` (UTC)

### `Outcome`
Fields: `solution_id`, `reporter_id`, `success` (bool), `environment?` (dict), `error_after?` (str), `time_saved_seconds?` (int), `notes?` (str), `weight` (float=1.0), `outcome_id` (auto-UUID), `created_at` (UTC)

## Constraints

- Do NOT remove existing models (`Agent`, `Thread`, `Comment`, `Vote`, `TokenTransaction`) yet — v1 compatibility layer comes later (task-030)
- Use `@dataclass(slots=True)` consistent with existing code
- No external imports beyond stdlib

## Files to modify

- `app/domain/models.py` — add three new dataclasses

## Verification

```bash
uv run pytest tests/unit/test_domain_models_v2.py -v
```

All tests from task-001 must pass (green).
