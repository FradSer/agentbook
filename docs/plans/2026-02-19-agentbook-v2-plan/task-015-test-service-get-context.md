# Task 015 — Test: AgentbookServiceV2.get_context()

**Type:** Red (test first)
**Depends-on:** task-004
**BDD refs:** Feature 5 Scenario "Tag-based navigation", Feature 5 Scenario "Traversing the knowledge graph by depth"

## Goal

Write failing unit tests for the `get_context()` method of `AgentbookServiceV2`.

## What to test

### Fetch problem context
- When `get_context(id=problem_id, include=["solutions", "similar"])` called
- Then returns `{"type": "problem", "data": {problem fields}, "solutions": [...], "similar": [...]}`
- And solutions are sorted by confidence descending

### Fetch solution context
- When `get_context(id=solution_id, include=["outcomes"])` called
- Then returns `{"type": "solution", "data": {solution fields}, "outcomes": [...]}`

### Not found
- When `get_context(id=non_existent_uuid)` called
- Then raises `NotFoundError`

### Include filtering
- `include=["solutions"]` → no `outcomes` or `similar` in response
- `include=[]` (empty) or omitted → returns all sections by default

### Related problems (knowledge graph)
- Given P301 linked to P300 as `root_cause`
- When `get_context(id=P301_id)` called
- Then response includes `"related_problems": [{"problem_id": P300_id, "relationship": "root_cause", ...}]`

## Files to create

- `tests/unit/test_service_get_context.py`

## Verification

```bash
uv run pytest tests/unit/test_service_get_context.py -v
```

Tests must fail (red) before implementation.
