# Task 009 — Test: AgentbookServiceV2.resolve()

**Type:** Red (test first)
**Depends-on:** task-004, task-006, task-008
**BDD refs:** Feature 1 all scenarios, Feature 6 Scenario "Solution posted at T=0 is searchable at T=0", Cross-Feature Scenario "No solution found triggers seamless problem creation"

## Goal

Write failing unit tests for the `resolve()` method on a new `AgentbookServiceV2` class. All tests use in-memory repositories (no DB, no network).

## Test setup

Use `conftest.py`-compatible fixtures:
- `InMemoryProblemRepository`, `InMemorySolutionRepository`, `InMemoryOutcomeRepository`
- Stub `EmbeddingProvider` returning deterministic embeddings (e.g., `[1.0, 0.0, ...]` for known strings)
- Authenticated `Agent` with a known `agent_id`

## What to test

### Happy path — match found
- Given knowledge base with solution S001 (Python 3.12, pydantic 2.5.0, confidence 0.92)
- When `resolve(problem={description="pydantic v1 import error", environment={"python": "3.12", "pydantic": "2.5.0"}})` called
- Then status is `"resolved"`, first solution is S001, response includes `problem_id`, `solutions[]` each with `confidence`, `outcome_rate`, `environment_match` fields

### Happy path — partial match (environment mismatch)
- Given S001 for Python 3.12, agent queries from Python 3.13
- When `resolve` called with Python 3.13 environment
- Then status is `"partial"`, S001 returned with `environment_match` < 1.0, annotated as partial

### No match — auto-register
- Given empty knowledge base
- When `resolve(problem={description="novel error X"}, options={auto_post: True})` called
- Then status is `"registered"`, a new `Problem` is created in the repository, `problem_id` returned in response, `solutions=[]`

### No match — no auto-register
- When `resolve` called with `auto_post=False` and no matching solutions
- Then status is `"no_solutions"`, no problem created, response includes pre-filled template

### Error signature fast path
- Given solution S002 indexed with `error_signature="ImportError: cannot import 'pydantic.v1'"`
- When `resolve` called with identical `error_signature`
- Then S002 appears in results via exact error signature match (not just semantic)

### Ranking — outcome rate dominates
- Given S001 (semantic similarity 0.95, outcome_rate 0.55) and S002 (similarity 0.80, outcome_rate 0.88)
- When `resolve` returns results
- Then S002 ranks above S001 (outcome_rate weighted 60%, similarity 40%)

### Empty description rejected
- When `resolve` called with `description=""` → raises `ValueError` or returns error status

## Files to create

- `tests/unit/test_service_resolve.py`

## Verification

```bash
uv run pytest tests/unit/test_service_resolve.py -v
```

Tests must fail (red) before implementation.
