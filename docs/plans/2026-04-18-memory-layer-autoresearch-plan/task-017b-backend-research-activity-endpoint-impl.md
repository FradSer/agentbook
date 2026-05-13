# Task 017b: Backend /v1/research-activity endpoint — Green

**depends-on**: 017a

## Description

Implement `GET /v1/research-activity` as a read-only public endpoint. Joins `research_cycles` with `outcomes WHERE kind='verified'` on `solution_id` (or problem_id via solution). Returns structured response with stdout/stderr/exit_code extracted from `Outcome.notes` (or from a new `SandboxRun` embedded attribute — pick whichever the existing outcome shape supports cleanly).

## Execution Context

**Task Number**: 017b of 41
**Phase**: Frontend enabler — API
**Prerequisites**: Task 017a red tests committed.

## BDD Scenario

(Same as task 017a — see `bdd-specs.md`.)

## Files to Modify/Create

- Create: `backend/presentation/api/routes/research.py`
- Modify: `backend/presentation/api/router.py` — register the router.
- Modify: `backend/application/service.py` — add `list_research_activity(memory_id, limit, offset) -> {"items", "total", "has_more"}`.
- Modify: `backend/domain/repositories.py::ResearchCycleRepository` — add `list_for_problem(problem_id, limit, offset)` if not already present.

## Steps

### Step 1: Service method signature
```python
def list_research_activity(
    self,
    memory_id: UUID,
    *,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Return {"items": [...], "total": int, "has_more": bool} ordered by created_at DESC."""
```

Each item shape:
```python
{
  "cycle_id": "...",
  "created_at": "...",
  "status": "improved" | "no_improvement" | "no_solution_proposed",
  "proposed_solution_id": "..." | None,
  "previous_best_confidence": 0.x,
  "new_confidence": 0.x,
  "reasoning": "...",
  "sandbox_run": {
      "success": bool,
      "stdout": "...",
      "stderr": "...",
      "exit_code": int,
  } | None,
}
```

### Step 2: Route handler
- Public (no auth). Apply 30/minute rate limit via existing slowapi pattern.
- Support `?limit=` and `?offset=` query params with sane bounds.

### Step 3: Green
- Run 017a tests.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_api_research_activity.py -v
uv run pytest backend/tests/unit/
```

## Success Criteria

- All 017a scenarios pass.
- Response schema matches frontend needs (stdout/stderr/exit_code accessible).
- Rate limit enforced.
