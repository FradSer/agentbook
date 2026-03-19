# Task 002: Domain Models — Implementation

**depends-on**: task-002-domain-models-test

## Description

Implement the unified domain model layer: update `models.py` to drop Thread/Comment/Vote and add review fields to Problem/Solution, update `repositories.py` protocols to drop V1 protocols and add new methods, update `errors.py` to drop V1-only errors, rename the token transaction field, and delete `scoring.py`.

## Execution Context

**Task Number**: 002b of 016
**Phase**: Foundation — Domain Layer
**Prerequisites**: Task 002 tests written (Red). Domain models test file exists.

## BDD Scenario

```gherkin
Scenario: Problem model has unified review fields
  Given the domain layer is imported
  When a Problem is created with description "Docker Alpine numpy error"
  Then the Problem has review_status = None
  And the Problem has review_score = None
  And the Problem has reviewed_at = None
  And the Problem has canonical_solution_id = None
  And the Problem has version = 1

Scenario: Default solution baseline is 0.3
  Given a Solution is created with author_verified=false
  When confidence is read
  Then its confidence is 0.3

Scenario: Author-verified solution baseline is 0.5
  Given a Solution is created with author_verified=true
  When confidence is read
  Then its confidence is 0.5
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature`

## Files to Modify/Create

- Modify: `app/domain/models.py`
- Modify: `app/domain/repositories.py`
- Modify: `app/application/errors.py`
- Delete: `app/domain/scoring.py`

## Steps

### Step 1: Update `app/domain/models.py`

Replace the entire file content to match the unified data model from the architecture:
- Keep `Agent`, `Outcome`, `ResearchCycle` dataclasses (unchanged)
- Update `Problem`: add `review_status`, `review_score`, `reviewed_at`, `canonical_solution_id`, `last_activity_at` fields
- Update `Solution`: add `review_status`, `review_score`, `reviewed_at` fields; remove `upvotes`, `downvotes`, `wilson_score`, `is_solution`, `path` fields; add `outcome_count`, `success_count`, `failure_count`; update `__post_init__` for author_verified baseline
- Update `TokenTransaction`: rename `related_comment_id` to `related_solution_id`
- Remove `Thread`, `Comment`, `Vote` dataclasses entirely

### Step 2: Update `app/domain/repositories.py`

- Remove `ThreadRepository`, `CommentRepository`, `VoteRepository` protocols
- Update `ProblemRepository`: add `delete()`, `find_unreviewed()`, `find_similar()` methods; ensure `search_similar()` exists
- Update `SolutionRepository`: add `delete()`, `find_unreviewed()`, `list_by_problem_ranked()`, `find_superseded()` methods
- Update `TokenTransactionRepository`: rename `clear_related_comment()` to `clear_related_solution()`

### Step 3: Delete `app/domain/scoring.py`

Remove the file. Any imports of this module in the codebase should be removed as well.

### Step 4: Update `app/application/errors.py`

Remove `DuplicateVoteError` and `SelfReportError` from the errors module.

### Step 5: Run tests (Green)

**Verification**: Run `uv run pytest tests/unit/test_domain_models.py -v --tb=short` and verify all tests pass.

### Step 6: Refactor and run full unit tests

**Verification**: Run `uv run pytest tests/unit/ --tb=short` and ensure no new failures were introduced beyond pre-existing V1 test failures.

## Verification Commands

```bash
uv run pytest tests/unit/test_domain_models.py -v --tb=short
uv run pytest tests/unit/ --tb=short -q
```

## Success Criteria

- All `test_domain_models.py` tests pass
- `Thread`, `Comment`, `Vote` removed from models.py
- `ThreadRepository`, `CommentRepository`, `VoteRepository` removed from repositories.py
- `scoring.py` deleted
- `DuplicateVoteError` removed from errors.py
- `related_solution_id` used in TokenTransaction
