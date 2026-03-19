# Task 006: Service — Problem/Solution CRUD — Implementation

**depends-on**: task-006-service-problem-crud-test

## Description

Update `AgentbookService` to implement `create_problem()`, `create_solution()`, `generate_problem_embedding()`, and update the `contribute()` method. Remove the V1 `create_thread()`, `create_comment()`, `vote_comment()` methods. Update the service constructor to remove `threads`, `comments`, `votes` parameters.

## Execution Context

**Task Number**: 006b of 016
**Phase**: Application Layer — Service CRUD
**Prerequisites**: Task 006 tests written (Red).

## BDD Scenario

```gherkin
Scenario: Agent creates problem with initial solution
  When alice calls contribute with valid description and solution_content
  Then a new problem is created with review_status=None
  And the solution has confidence 0.5 when author_verified=True
  And problem solution_count = 1
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature` (Feature 2)

## Files to Modify/Create

- Modify: `app/application/service.py`

## Steps

### Step 1: Update `AgentbookService.__init__`

Remove `threads: ThreadRepository`, `comments: CommentRepository`, `votes: VoteRepository` from the constructor. Ensure the constructor accepts `problems`, `solutions`, `outcomes`, `transactions`, `research_cycles` repositories only.

### Step 2: Implement `create_problem()`

Add `create_problem(author_id, description, error_signature=None, environment=None, tags=None) -> Problem`:
- Call `self._ensure_agent_exists(author_id)`
- Call `check_spam(description, "problem")`; raise `ValueError(gate.reason)` if not passed
- Create a `Problem` dataclass instance with `review_status=None`
- Call `self._problems.add(problem)`
- Return the problem

### Step 3: Implement `create_solution()`

Add `create_solution(problem_id, author_id, content, steps=None, author_verified=False, parent_solution_id=None) -> Solution`:
- Verify problem exists and is viewable (use `_can_view_problem`)
- Call `check_spam(content, "solution", {"steps": steps})`; raise `ValueError` if not passed
- Create a `Solution` with `review_status=None`; `Solution.__post_init__` handles author_verified baseline
- Increment `problem.solution_count` and update `problem.last_activity_at`
- Call `self._solutions.add(solution)` and `self._problems.update(problem)`
- Return the solution

### Step 4: Implement `generate_problem_embedding()`

Add `generate_problem_embedding(problem_id: UUID) -> None`:
- Return early if `self._embedding_provider is None`
- Get problem, embed its description, update problem
- This replaces `generate_thread_embedding()`

### Step 5: Update `contribute()`

Update the existing `contribute()` method to:
- Use `create_problem()` and `create_solution()` internally
- Return `{"status": "knowledge_created", ...}` when solution is provided
- Return `{"status": "problem_created", ...}` when no solution
- Return `{"status": "similar_exists", ...}` when similar problem found via embedding

### Step 6: Remove V1 methods

Remove or stub out: `create_thread()`, `get_thread_detail()`, `list_threads()`, `create_comment()`, `vote_comment()`, `generate_thread_embedding()`, `update_thread_review()`, `update_comment_review()`.

### Step 7: Run tests (Green)

**Verification**: Run `uv run pytest tests/unit/test_service_problem_crud.py -v --tb=short` and verify all pass.

## Verification Commands

```bash
uv run pytest tests/unit/test_service_problem_crud.py -v --tb=short
uv run pytest tests/unit/ -q --tb=short
```

## Success Criteria

- All `test_service_problem_crud.py` tests pass
- `create_problem()`, `create_solution()` implemented with gate integration
- V1 methods removed from service
