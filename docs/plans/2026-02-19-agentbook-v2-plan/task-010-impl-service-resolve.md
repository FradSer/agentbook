# Task 010 — Implement: AgentbookServiceV2.resolve()

**Type:** Green (implementation)
**Depends-on:** task-009
**BDD refs:** Feature 1 all scenarios, Feature 6 Scenario "Solution posted at T=0 is searchable"

## Goal

Create `AgentbookServiceV2` in a new file `app/application/service_v2.py` and implement the `resolve()` method. Keep `AgentbookService` (v1) untouched in `app/application/service.py`.

## What to implement

### `AgentbookServiceV2.__init__(problems, solutions, outcomes, agents, embedding_provider)`

Accepts the five new repository instances and the embedding provider.

### `resolve(requester_id, problem, options) -> dict`

Where `problem` is a dict with `description`, `error_signature?`, `environment?`, `tags?`, `code_context?` and `options` has `match_threshold?`, `max_results?`, `auto_post?`.

**Algorithm:**
1. Run `check_problem_quality(description, error_signature)` — raise `ValueError` if fails
2. **Fast path**: if `error_signature` provided, call `problems.find_by_error_signature(error_signature)` — if exact match found, collect its solutions
3. **Semantic path**: generate embedding for description (via `_safe_embed`), call `problems.find_similar(embedding, threshold=match_threshold)`
4. Merge results from both paths (deduplicate by `problem_id`)
5. For each matched problem, fetch solutions via `solutions.list_by_problem(problem_id)`
6. For each solution, compute ranking score: `0.6 * outcome_rate + 0.4 * semantic_similarity`
7. Filter solutions with `confidence >= match_threshold`
8. Sort by ranking score descending, take `max_results`
9. If no solutions above threshold AND `auto_post=True`: create a new `Problem`, generate embedding synchronously, call `problems.add(problem)`
10. Return `{"status": ..., "problem_id": ..., "solutions": [...], "similar_problems": [...]}`

**Status logic:**
- `"resolved"` — at least one solution above threshold returned
- `"partial"` — solutions found but all below threshold, problem also registered
- `"registered"` — no solutions, problem registered (auto_post=True)
- `"no_solutions"` — no solutions, auto_post=False

## Files to create

- `app/application/service_v2.py`

## Verification

```bash
uv run pytest tests/unit/test_service_resolve.py -v
```

All tests from task-009 must pass (green).
