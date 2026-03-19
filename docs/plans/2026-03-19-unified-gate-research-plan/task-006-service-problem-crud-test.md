# Task 006: Service — Problem/Solution CRUD — Test

**depends-on**: task-004-in-memory-repos-impl, task-005-unified-gate-impl

## Description

Write unit tests for the `AgentbookService` problem/solution creation methods. Tests drive the implementation of `create_problem()`, `create_solution()`, and the updated `contribute()` MCP method. Uses in-memory repositories (no database needed).

## Execution Context

**Task Number**: 006a of 016
**Phase**: Application Layer — Service CRUD
**Prerequisites**: In-memory repos implemented (Task 004), gate implemented (Task 005).

## BDD Scenario

```gherkin
Scenario: Agent creates problem with initial solution
  When alice calls contribute with description "ModuleNotFoundError importing numpy in Docker Alpine"
  And solution_content "Install numpy with apk dependencies first"
  And author_verified=true
  Then a new problem is created with status "knowledge_created"
  And the problem has solution_count 1
  And the initial solution has confidence 0.5 (author_verified baseline)
  And both problem and solution have review_status=None (pending)

Scenario: Agent creates problem without initial solution
  When alice calls contribute with description "Segmentation fault using multiprocessing with fork on macOS"
  And no solution_content
  Then a new problem is created with status "problem_created"
  And the problem has solution_count 0

Scenario: Agent contributes solution to existing problem
  Given problem "prob-1" exists and is approved
  When bob calls contribute with a solution for "prob-1"
  Then a new solution is added to "prob-1"
  And the solution has confidence 0.3 (default baseline)
  And problem "prob-1" solution_count increments by 1
  And the solution has review_status=None (pending)

Scenario: Contribute detects similar existing problems
  Given problem "prob-1" exists with description embedding
  When alice contributes a problem with similarity score > 0.9
  Then the response status is "similar_exists"
  And the response includes existing_problems containing "prob-1"

Scenario: create_problem raises ValueError when gate rejects
  Given a description "help" (too short, < 20 chars)
  When create_problem is called
  Then ValueError is raised with reason "Problem description too short"
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature` (Feature 2 — Creation scenarios)

## Files to Modify/Create

- Create: `tests/unit/test_service_problem_crud.py`

## Steps

### Step 1: Write tests (Red)

In `tests/unit/test_service_problem_crud.py`, write tests using in-memory repositories (rely on conftest autouse fixture). Test:
1. `service.create_problem(author_id, description)` returns a `Problem` with `review_status=None`
2. `service.create_problem(author_id, "help")` raises `ValueError` (gate rejection)
3. `service.create_solution(problem_id, author_id, content)` returns a `Solution` with `confidence=0.3`
4. `service.create_solution(problem_id, author_id, content, author_verified=True)` returns `confidence=0.5`
5. `service.create_solution(problem_id, ...)` increments `problem.solution_count`
6. `service.contribute(...)` with `solution_content` creates both problem and solution, returns `{"status": "knowledge_created"}`
7. `service.contribute(...)` without solution returns `{"status": "problem_created"}`
8. `service.create_solution` with rejected gate content raises `ValueError`
9. `service.generate_problem_embedding(problem_id)` updates the problem embedding when provider is set

**Verification**: Run `uv run pytest tests/unit/test_service_problem_crud.py --tb=short` and verify failures.

## Verification Commands

```bash
uv run pytest tests/unit/test_service_problem_crud.py -v --tb=short
```

## Success Criteria

- All tests fail (Red phase complete)
- Failures confirm missing `create_problem`/`create_solution` methods or wrong behavior in service
