# Task 003: ORM Models & Migration — Implementation

**depends-on**: task-003-orm-migration-test

## Description

Update `sqlalchemy_models.py` to match the unified schema (drop V1 ORM models, add review fields to ProblemORM and SolutionORM, add `canonical_solution_id` to ProblemORM, rename `related_comment_id` to `related_solution_id`), update `sqlalchemy_repositories.py` to remove V1 repository implementations, and create the Alembic migration `f5g6h7i8j9k0_unify_v1_v2.py`.

## Execution Context

**Task Number**: 003b of 016
**Phase**: Foundation — Infrastructure (ORM + Migration)
**Prerequisites**: Task 003 ORM tests written (Red).

## BDD Scenario

```gherkin
Scenario: Database CHECK constraint prevents self-loop
  When a solution is created with parent_solution_id equal to its own solution_id
  Then the database rejects the insert with a CHECK constraint violation

Scenario: ProblemORM has review fields
  Given the ORM module is imported
  When ProblemORM is inspected
  Then ProblemORM has columns: review_status, review_score, reviewed_at, canonical_solution_id
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature`

## Files to Modify/Create

- Modify: `app/infrastructure/persistence/sqlalchemy_models.py`
- Modify: `app/infrastructure/persistence/sqlalchemy_repositories.py`
- Create: `alembic/versions/f5g6h7i8j9k0_unify_v1_v2.py`

## Steps

### Step 1: Update `sqlalchemy_models.py`

- Remove `ThreadORM`, `CommentORM`, `VoteORM` classes
- Update `ProblemORM`: add `review_status`, `review_score`, `reviewed_at`, `canonical_solution_id` columns; add index `ix_problems_review_status` (partial: `review_status IS NULL OR review_status = 'error'`); add `last_activity_at` column; add `ix_problems_canonical_solution_id` index
- Update `SolutionORM`: add `review_status`, `review_score`, `reviewed_at` columns; add index `ix_solutions_review_status` (partial); ensure `CheckConstraint("parent_solution_id != solution_id", name="ck_no_self_parent")` is in `__table_args__`
- Update `TokenTransactionORM`: rename `related_comment_id` to `related_solution_id`, update FK to point to `solutions.solution_id`
- Update `_to_problem_domain()` and `_to_solution_domain()` mapper functions to include new fields

### Step 2: Update `sqlalchemy_repositories.py`

- Remove `SQLAlchemyThreadRepository`, `SQLAlchemyCommentRepository`, `SQLAlchemyVoteRepository`
- Update `SQLAlchemyProblemRepository`: implement `delete()`, `find_unreviewed()`, `find_similar()`, `find_research_candidates()` methods
- Update `SQLAlchemySolutionRepository`: implement `delete()`, `find_unreviewed()`, `list_by_problem_ranked()`, `find_superseded()` methods
- Update `SQLAlchemyTokenTransactionRepository`: rename `clear_related_comment()` to `clear_related_solution()`

### Step 3: Create Alembic migration

Create `alembic/versions/f5g6h7i8j9k0_unify_v1_v2.py` with:
- `upgrade()`: add review columns to problems/solutions, add canonical_solution_id, migrate threads→problems, migrate comments→solutions, rename related_comment_id, drop votes/comments/threads tables, create partial indexes
- `downgrade()`: raises `NotImplementedError`
- Revision ID: `f5g6h7i8j9k0`
- Down revision: the most recent existing migration

Verify the down_revision matches the current head by running `uv run alembic heads` first.

### Step 4: Run tests (Green)

**Verification**: Run `uv run pytest tests/unit/test_orm_models.py -v --tb=short` and verify all pass.

### Step 5: Verify migration syntax

**Verification**: Run `uv run alembic check` (does not modify DB, just validates migration chain).

## Verification Commands

```bash
uv run pytest tests/unit/test_orm_models.py -v --tb=short
uv run alembic check
uv run pytest tests/unit/ -q --tb=short
```

## Success Criteria

- All `test_orm_models.py` tests pass
- Migration file created with correct up/downgrade
- No new unit test regressions
