# Task 012 — Implement: AgentbookServiceV2.contribute()

**Type:** Green (implementation)
**Depends-on:** task-011
**BDD refs:** Feature 2 all scenarios, Feature 6 Scenario "Solution posted at T=0 is searchable"

## Goal

Add `contribute()` to `AgentbookServiceV2` in `app/application/service_v2.py`.

## What to implement

### `contribute(author_id, problem_dict, solution_dict | None) -> dict`

**Algorithm:**
1. Run `check_problem_quality(problem_dict["description"], problem_dict.get("error_signature"))` — raise `ValueError` on failure
2. If `solution_dict` provided, run `check_solution_quality(solution_dict["content"], solution_dict.get("steps"))` — raise `ValueError` on failure
3. **Duplicate detection**: generate embedding for description, call `problems.find_similar(embedding, threshold=0.9)`, collect near-duplicates
4. Create new `Problem` from `problem_dict` — set embedding synchronously via `_safe_embed` if provider available
5. Call `problems.add(new_problem)` — immediately persistent
6. If `solution_dict` provided:
   - Create `Solution` with `initial_confidence = 0.5 if verified else 0.3`
   - Call `solutions.add(new_solution)` — immediately persistent
   - Update `new_problem.solution_count += 1`, `problems.update(new_problem)`
7. If near-duplicates found, link them (store in related_problems association — can be a simple list field on `Problem` or a separate dict in the repo for now)
8. Return `{"status": ..., "problem_id": ..., "solution_id": ..., "existing_problems": [...] | None}`

## Files to modify

- `app/application/service_v2.py` — add `contribute()` method

## Verification

```bash
uv run pytest tests/unit/test_service_contribute.py -v
```

All tests from task-011 must pass (green).
