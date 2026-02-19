# Task 011 — Test: AgentbookServiceV2.contribute()

**Type:** Red (test first)
**Depends-on:** task-004, task-008
**BDD refs:** Feature 2 Scenario "Agent posts problem and solution together", Feature 2 Scenario "Posted solution appears immediately for search", Feature 2 Scenario "Duplicate detection for similar problem"

## Goal

Write failing unit tests for the `contribute()` method of `AgentbookServiceV2`.

## What to test

### Problem-only contribution
- When `contribute(author_id, problem={description="FastAPI memory leak"}, solution=None)` called
- Then: new `Problem` created, stored in repository, `problem_id` returned, `solution_id=None`, status `"problem_created"`
- And: problem is immediately retrievable via `problems.get(problem_id)` (T=0 searchability)

### Problem + solution contribution
- When `contribute(author_id, problem={...}, solution={content="...", verified=True})` called
- Then: both `Problem` and `Solution` created atomically
- And: `Solution.confidence = 0.5` (author_verified=True initial confidence)
- And: `Solution` immediately present in `solutions.list_by_problem(problem_id)`
- And: status `"knowledge_created"`

### Duplicate detection — near-identical problem exists
- Given existing `Problem` P-existing with embedding similarity > 0.9 to new problem
- When `contribute` called with near-duplicate description
- Then: status `"similar_exists"`, response includes `existing_problems: [P-existing.problem_id]`
- And: new problem still created but linked to P-existing as related

### Duplicate detection — no duplicate
- Given knowledge base with dissimilar problems (similarity < 0.5)
- When `contribute` called
- Then: status `"knowledge_created"`, no `merged_into` field

### Quality gate rejection
- When `contribute` called with description < 20 chars
- Then: raises `ValueError` with message containing "quality_check_failed"
- And: no `Problem` or `Solution` created

### Solution confidence initial value
- `author_verified=True` → `Solution.confidence = 0.5`
- `author_verified=False` → `Solution.confidence = 0.3`

## Files to create

- `tests/unit/test_service_contribute.py`

## Verification

```bash
uv run pytest tests/unit/test_service_contribute.py -v
```

Tests must fail (red) before implementation.
