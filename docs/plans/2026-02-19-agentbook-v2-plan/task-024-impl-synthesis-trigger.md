# Task 024 — Implement: ReviewerAgent V2 Synthesis Trigger

**Type:** Green (implementation)
**Depends-on:** task-023
**BDD refs:** Feature 4 Scenario "Synthesis triggered by similarity threshold not time", Feature 4 Scenario "Synthesis does not merge environment-variant solutions"

## Goal

Implement synthesis trigger logic in `agent/src/synthesis.py`. Pure functions, no I/O.

## What to implement

### `should_trigger_synthesis(solutions, similarity_matrix) -> bool`

Checks in order:
1. If `len(solutions) >= 10` → `True`
2. If any solution has `confidence < 0.3 and outcome_count >= 10` → `True`
3. Count pairs with `similarity_matrix[(s_i.solution_id, s_j.solution_id)] > 0.85` — if 3+ solutions in such a cluster → `True`
4. Environment divergence check: for each candidate cluster, check `environment_scores` divergence — if solutions serve different environments (e.g., one for Python 3.10 only, one for 3.12 only based on outcome data), exclude from cluster → `False` if cluster dissolves
5. Otherwise → `False`

### `find_synthesis_candidates(problems, solutions_by_problem, similarity_fn) -> list[list[Solution]]`

For each problem:
1. Fetch its solutions (exclude those with `canonical_id` set)
2. Compute pairwise similarity matrix using `similarity_fn` (cosine similarity of embeddings or solution content)
3. Use a simple greedy clustering: start with highest-similarity pair, grow cluster while pairwise similarity > 0.85
4. Apply `should_trigger_synthesis` to each cluster
5. Return list of clusters that passed

## Files to create

- `agent/src/synthesis.py`

## Verification

```bash
uv run pytest tests/unit/test_synthesis_trigger.py -v
```

All tests from task-023 must pass (green).
