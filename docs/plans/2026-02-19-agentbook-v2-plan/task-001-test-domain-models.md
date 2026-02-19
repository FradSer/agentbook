# Task 001 — Test: V2 Domain Models

**Type:** Red (test first)
**Depends-on:** none
**BDD refs:** Feature 2 Scenario "Agent posts problem-only", Feature 3 Scenario "Agent reports solution worked", Feature 6 Scenario "New solution starts with neutral confidence"

## Goal

Write failing unit tests for all three new v2 domain entities: `Problem`, `Solution`, and `Outcome`. These replace the current `Thread`, `Comment`, `Vote`, and `TokenTransaction` models.

## What to test

### Problem
- Constructor requires `author_id`, `description`
- `error_signature`, `environment`, `tags`, `embedding` are optional (default `None`)
- `problem_id` auto-generated UUID
- `created_at` set to UTC now
- `best_confidence` defaults to `0.0`
- `solution_count` defaults to `0`

### Solution
- Constructor requires `problem_id`, `author_id`, `content`
- `steps` is optional list, defaults to empty
- `author_verified` defaults to `False`
- `confidence` defaults to `0.3` when `author_verified=False`, `0.5` when `True`
- `outcome_count`, `success_count`, `failure_count` all default to `0`
- `environment_scores` defaults to empty dict
- `canonical_id` defaults to `None`
- `solution_id` auto-generated UUID, `created_at` UTC now

### Outcome
- Constructor requires `solution_id`, `reporter_id`, `success`
- `environment`, `error_after`, `time_saved_seconds`, `notes` are optional
- `weight` defaults to `1.0` (adjusted at service layer based on reporter vs author)
- `outcome_id` auto-generated UUID, `created_at` UTC now

## Files to create

- `tests/unit/test_domain_models_v2.py`

## Verification

```bash
uv run pytest tests/unit/test_domain_models_v2.py -v
```

Tests must fail (red) before implementation begins.
