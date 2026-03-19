# Task 008: Service — Agentbook View — Implementation

**depends-on**: task-008-service-agentbook-view-test

## Description

Implement `get_agentbook()` in `AgentbookService` — the primary read path that shows the canonical solution first. Update `search()` to operate on problems instead of threads, returning best solution for each result. Add `_pick_best_solution()` helper.

## Execution Context

**Task Number**: 008b of 016
**Phase**: Application Layer — Agentbook View
**Prerequisites**: Task 008 tests written (Red).

## BDD Scenario

```gherkin
Scenario: Canonical solution shown first in agentbook view
  Given problem "prob-1" has canonical_solution_id = "canonical-1"
  When get_agentbook is called
  Then canonical_solution field is populated with "canonical-1" data
  And solution_history lists all other approved solutions
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature` (Feature 2)

## Files to Modify/Create

- Modify: `app/application/service.py`

## Steps

### Step 1: Implement `get_agentbook()`

Add `get_agentbook(problem_id: UUID, viewer_id: UUID | None = None) -> dict`:
- Get problem; raise `NotFoundError` if not found
- Apply `_can_view_problem(problem, viewer_id)` check
- Get all solutions via `self._solutions.list_by_problem(problem_id)`
- Filter to approved solutions
- If `problem.canonical_solution_id` is set, extract canonical solution and fetch its outcomes
- `solution_history` = approved solutions excluding the canonical
- Return dict with: `problem_id`, `description`, `error_signature`, `environment`, `tags`, `review_status`, `best_confidence`, `solution_count`, `canonical_solution`, `solution_history`, `created_at`, `last_activity_at`

### Step 2: Add `_pick_best_solution()` helper

Add `_pick_best_solution(problem_id: UUID) -> dict | None`:
- Get all approved solutions for the problem
- Return the one with highest confidence as a dict with `solution_id`, `content_preview` (first 200 chars), `confidence`, `outcome_count`, `success_count`

### Step 3: Update `search()`

Update `search(query: str, limit: int, error_log: str | None = None) -> dict`:
- Use `self._problems.search_similar(query_embedding)` instead of thread search
- Filter results to approved problems only
- Include `best_solution` dict from `_pick_best_solution()` in each result
- Keyword fallback: scan `self._problems.list_all()` for approved problems matching query terms

### Step 4: Run tests (Green)

**Verification**: Run `uv run pytest tests/unit/test_service_agentbook_view.py -v --tb=short` and verify all pass.

## Verification Commands

```bash
uv run pytest tests/unit/test_service_agentbook_view.py -v --tb=short
uv run pytest tests/unit/ -q --tb=short
```

## Success Criteria

- All `test_service_agentbook_view.py` tests pass
- `get_agentbook()` returns canonical_solution + solution_history correctly
- Only approved content appears in search results
