# Task 023 — Test: ReviewerAgent V2 Synthesis Trigger

**Type:** Red (test first)
**Depends-on:** task-004
**BDD refs:** Feature 4 Scenario "ReviewerAgent detects 3+ similar solutions and synthesizes", Feature 4 Scenario "Synthesis triggered by similarity threshold not time"

## Goal

Write failing unit tests for the logic that determines WHEN to trigger solution synthesis. Pure function tested in isolation — no LLM calls in these tests.

## What to test

### `should_trigger_synthesis(solutions: list[Solution], similarity_matrix: dict) -> bool`

- 4 solutions with pairwise similarity all > 0.85 → returns `True`
- Only 2 solutions with similarity > 0.85 → returns `False` (minimum is 3)
- 10 solutions regardless of similarity → returns `True`
- 4 solutions but similarities all < 0.8 → returns `False`
- 1 solution with confidence < 0.3 and 10+ outcomes → returns `True` (needs replacement)

### `find_synthesis_candidates(problems: list[Problem], solutions_by_problem: dict, similarity_fn) -> list[list[Solution]]`

- Returns groups of solutions that meet synthesis criteria
- Each group contains 3+ similar solutions
- Groups are distinct (no solution in two groups)
- Solutions with `canonical_id` set (already synthesized) are excluded

### No synthesis for environment-variant solutions
- Given S300 (Python 3.12, confidence 0.90) and S301 (Python 3.10, confidence 0.85) with similarity 0.92 on problem text
- But S300.environment_scores["python_3.10"] = 0.1 (works badly on 3.10)
- When evaluating synthesis → `should_trigger_synthesis` returns `False` (different environment targets)

## Files to create

- `tests/unit/test_synthesis_trigger.py`

## Verification

```bash
uv run pytest tests/unit/test_synthesis_trigger.py -v
```

Tests must fail (red) before implementation.
