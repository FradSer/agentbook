# Task 003: ORM Models & Migration — Test

**depends-on**: task-002-domain-models-impl

## Description

Write tests for the updated ORM models (ProblemORM and SolutionORM must have review fields; ThreadORM/CommentORM/VoteORM must be absent) and for the Alembic migration (new columns appear, old tables are dropped, FK integrity is maintained).

## Execution Context

**Task Number**: 003a of 016
**Phase**: Foundation — Infrastructure (ORM + Migration)
**Prerequisites**: Domain models updated (Task 002 complete).

## BDD Scenario

```gherkin
Scenario: Database CHECK constraint prevents self-loop
  When a solution is created with parent_solution_id equal to its own solution_id
  Then the database rejects the insert with a CHECK constraint violation

Scenario: ProblemORM has review fields
  Given the ORM module is imported
  When ProblemORM is inspected
  Then ProblemORM has columns: review_status, review_score, reviewed_at, canonical_solution_id

Scenario: SolutionORM has review fields
  Given the ORM module is imported
  When SolutionORM is inspected
  Then SolutionORM has columns: review_status, review_score, reviewed_at

Scenario: ThreadORM, CommentORM, VoteORM do not exist
  Given the ORM module is imported
  When the module's public names are inspected
  Then importing ThreadORM raises AttributeError
  And importing CommentORM raises AttributeError
  And importing VoteORM raises AttributeError
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature` (Feature 2 — "Database CHECK constraint prevents self-loop")

## Files to Modify/Create

- Create: `tests/unit/test_orm_models.py`

## Steps

### Step 1: Write ORM model tests (Red)

In `tests/unit/test_orm_models.py`, write tests for:
1. `ProblemORM` has `review_status`, `review_score`, `reviewed_at`, `canonical_solution_id` columns
2. `SolutionORM` has `review_status`, `review_score`, `reviewed_at` columns
3. `SolutionORM.__table_args__` includes `CheckConstraint("parent_solution_id != solution_id", ...)`
4. `TokenTransactionORM` has `related_solution_id` column (not `related_comment_id`)
5. `ThreadORM`, `CommentORM`, `VoteORM` cannot be imported from `app.infrastructure.persistence.sqlalchemy_models`

Write an integration test (marked `@pytest.mark.smoke`) that:
- Creates a SolutionORM with `parent_solution_id == solution_id`
- Verifies the database raises an IntegrityError

### Step 2: Write migration structure test

Write a test that imports the migration file `alembic/versions/f5g6h7i8j9k0_unify_v1_v2.py` and verifies:
- The `upgrade()` function exists
- The `downgrade()` function raises `NotImplementedError`

**Verification**: Run `uv run pytest tests/unit/test_orm_models.py --tb=short` and verify failures.

## Verification Commands

```bash
uv run pytest tests/unit/test_orm_models.py -v --tb=short
```

## Success Criteria

- All `test_orm_models.py` tests fail (Red phase complete)
- Failures confirm missing review columns, missing CHECK constraint, or presence of old ORM models
