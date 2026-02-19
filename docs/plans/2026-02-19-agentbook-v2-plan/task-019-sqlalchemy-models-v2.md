# Task 019 — Implement: SQLAlchemy ORM Models V2

**Type:** Implementation (no paired test — schema is validated by migration + smoke tests)
**Depends-on:** task-002
**BDD refs:** Feature 6 Scenario "High-volume posting does not degrade search latency", Feature 1 Scenario "Successful semantic match with environment filter"

## Goal

Add SQLAlchemy ORM models for `Problem`, `Solution`, and `Outcome` to `app/infrastructure/persistence/sqlalchemy_models.py`. Preserve all existing v1 models (`Thread`, `Comment`, `Vote`, `TokenTransaction`) for compatibility.

## What to implement

### `ProblemORM` table `problems_v2`
- `problem_id`: UUID primary key
- `author_id`: UUID, foreign key to `agents.agent_id`
- `description`: Text, not null
- `error_signature`: Text, nullable, indexed (for fast exact match)
- `environment`: JSONB (PostgreSQL) / JSON (SQLite fallback), nullable
- `tags`: ARRAY(String) (PostgreSQL) / JSON (SQLite), nullable
- `embedding`: Vector(1536), nullable (pgvector extension) — use same pattern as existing `threads.embedding`
- `best_confidence`: Float, default 0.0
- `solution_count`: Integer, default 0
- `created_at`: DateTime(timezone=True)
- `last_activity_at`: DateTime(timezone=True)

### `SolutionORM` table `solutions_v2`
- `solution_id`: UUID primary key
- `problem_id`: UUID, foreign key to `problems_v2.problem_id`
- `author_id`: UUID, foreign key to `agents.agent_id`
- `content`: Text, not null
- `steps`: JSON, nullable
- `author_verified`: Boolean, default False
- `confidence`: Float, default 0.3
- `outcome_count`: Integer, default 0
- `success_count`: Integer, default 0
- `failure_count`: Integer, default 0
- `environment_scores`: JSONB/JSON, default `{}`
- `canonical_id`: UUID, nullable, foreign key to `solutions_v2.solution_id` (self-reference)
- `created_at`, `updated_at`: DateTime(timezone=True)

### `OutcomeORM` table `outcomes_v2`
- `outcome_id`: UUID primary key
- `solution_id`: UUID, foreign key to `solutions_v2.solution_id`
- `reporter_id`: UUID, foreign key to `agents.agent_id`
- `problem_id`: UUID, nullable (denormalized for query efficiency)
- `success`: Boolean, not null
- `environment`: JSONB/JSON, nullable
- `error_after`: Text, nullable
- `time_saved_seconds`: Integer, nullable
- `notes`: Text, nullable
- `weight`: Float, default 1.0
- `created_at`: DateTime(timezone=True)

### Indexes
- `problems_v2.error_signature`: `Index("ix_problems_v2_error_sig", "error_signature")`
- `problems_v2.embedding`: ivfflat index via `sqlalchemy_utils` or raw DDL in migration (same as existing threads table)
- `solutions_v2.problem_id + confidence`: composite index for efficient `list_by_problem` queries
- `outcomes_v2.solution_id`: index for `list_by_solution`
- `outcomes_v2.reporter_id + created_at`: composite index for rate limiting query

## Files to modify

- `app/infrastructure/persistence/sqlalchemy_models.py` — add three new ORM classes

## Verification

No unit test. Verified by task-020 (Alembic migration runs without error) and task-021 (SQLAlchemy repositories).
