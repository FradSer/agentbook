# Task 025 — Test: Solution Synthesis Pipeline

**Type:** Red (test first)
**Depends-on:** task-024
**BDD refs:** Feature 4 Scenario "ReviewerAgent detects 3+ similar solutions and synthesizes", Feature 4 Scenario "Synthesized solution inherits outcome scores from sources", Feature 4 Scenario "Original solutions marked as superseded but still searchable"

## Goal

Write failing unit tests for the synthesis pipeline that takes a cluster of similar solutions and produces a canonical solution. LLM call is stubbed.

## What to test

### `synthesize_solutions(solutions: list[Solution], problem: Problem, llm_fn: Callable) -> Solution`

**Canonical solution is created:**
- Given 4 similar solutions S200-S203 for pydantic v2 migration
- `llm_fn` stub returns a synthesized content string
- When `synthesize_solutions(solutions=[S200, S201, S202, S203], problem=P100, llm_fn=stub)` called
- Then returns a new `Solution` with `canonical_id=None` (itself is canonical), `content=stub_return`, type="synthesized"

**Confidence inheritance:**
- Given source solutions with combined 120 outcomes (95 successes)
- When canonical created
- Then `canonical.confidence ≈ 95/120 = 0.79` (inherited from sources)
- And `canonical.outcome_count = 120`, `canonical.success_count = 95`

**Source solutions marked superseded:**
- `_mark_superseded(solutions, canonical_id)` → sets `solution.canonical_id = canonical.solution_id` on all sources

**Stub LLM call receives correct prompt:**
- `llm_fn` is called with a prompt containing all source solution contents
- Prompt includes the parent problem description

### `run_synthesis_cycle(service_v2, embedding_fn, llm_fn) -> dict`
- Event-driven: finds all candidate clusters, runs synthesis for each
- Returns `{"synthesized": N, "skipped": M}` summary
- Does not run if no clusters meet threshold (skipped=all)

## Files to create

- `tests/unit/test_solution_synthesis.py`

## Verification

```bash
uv run pytest tests/unit/test_solution_synthesis.py -v
```

Tests must fail (red) before implementation.
