# Task 002: Domain Models — Test

**depends-on**: task-001-setup

## Description

Write unit tests for the unified domain models. Tests verify that `Problem` and `Solution` have the required new fields (`review_status`, `review_score`, `reviewed_at`, `canonical_solution_id`, etc.), that `Thread`, `Comment`, and `Vote` models no longer exist, that `scoring.py` is deleted, and that `DuplicateVoteError` is removed from errors.

## Execution Context

**Task Number**: 002a of 016
**Phase**: Foundation — Domain Layer
**Prerequisites**: Task 001 complete (conftest updated, settings updated).

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

Scenario: Solution baseline confidence depends on author_verified
  Given a Solution is created with author_verified=false
  Then its confidence is 0.3
  When a Solution is created with author_verified=true
  Then its confidence is 0.5

Scenario: Solution has review fields
  Given a Solution is created
  Then the Solution has review_status = None
  And the Solution has review_score = None
  And the Solution has reviewed_at = None

Scenario: Thread, Comment, Vote no longer exist
  Given the domain models module is imported
  Then importing Thread raises ImportError or AttributeError
  And importing Comment raises ImportError or AttributeError
  And importing Vote raises ImportError or AttributeError
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature` (Feature 1 + Feature 2)

## Files to Modify/Create

- Create: `tests/unit/test_domain_models.py`

## Steps

### Step 1: Write failing tests (Red)

In `tests/unit/test_domain_models.py`, write tests for:
1. `Problem` model has fields: `review_status`, `review_score`, `reviewed_at`, `canonical_solution_id`, `best_confidence`, `solution_count`, `version`, `last_activity_at`
2. `Solution` model has fields: `review_status`, `review_score`, `reviewed_at`, `parent_solution_id`, `canonical_id`, `outcome_count`, `success_count`, `failure_count`
3. `Solution.__post_init__` sets confidence=0.5 when `author_verified=True`
4. `Thread`, `Comment`, `Vote` cannot be imported from `app.domain.models`
5. `app.domain.scoring` module does not exist (or raises ImportError)
6. `app.application.errors` has no `DuplicateVoteError`
7. `TokenTransaction.related_solution_id` exists (not `related_comment_id`)
8. `ProblemRepository` protocol has `delete()`, `find_unreviewed()`, `find_similar()` methods
9. `SolutionRepository` protocol has `delete()`, `find_unreviewed()`, `list_by_problem_ranked()` methods

**Verification**: Run `uv run pytest tests/unit/test_domain_models.py --tb=short` and verify failures.

### Step 2: Verify failures are correct

Confirm tests fail because the current models still have Thread/Comment/Vote, lack review fields, etc.

## Verification Commands

```bash
uv run pytest tests/unit/test_domain_models.py -v --tb=short
```

## Success Criteria

- All tests in `test_domain_models.py` fail (Red phase complete)
- Failure messages indicate the domain models need to be updated (not import errors in the test itself)
