# Task 020 — Implement: Alembic Migration for V2 Schema

**Type:** Implementation
**Depends-on:** task-019
**BDD refs:** Feature 6 Scenario "Solution posted at T=0 is searchable"

## Goal

Generate and validate an Alembic migration that creates the three new v2 tables (`problems_v2`, `solutions_v2`, `outcomes_v2`) without touching existing v1 tables.

## What to implement

### Generate migration

```bash
uv run alembic revision --autogenerate -m "add v2 resolution graph tables"
```

### Review and edit the generated migration

Manually inspect the generated file in `alembic/versions/` and ensure:
1. Only `problems_v2`, `solutions_v2`, `outcomes_v2` tables are created (no v1 table changes)
2. `pgvector` extension already enabled — do NOT add `CREATE EXTENSION` (already exists from v1 migration)
3. ivfflat index for `problems_v2.embedding` added in `upgrade()`:
   ```sql
   CREATE INDEX ix_problems_v2_embedding ON problems_v2
   USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
   ```
4. All foreign key constraints reference correct v1 table (`agents`) — do not drop or alter it
5. `downgrade()` drops tables in reverse dependency order: `outcomes_v2` → `solutions_v2` → `problems_v2`

### Test migration round-trip

Run upgrade and downgrade against a test PostgreSQL instance (can use Docker):

```bash
make smoke
```

Or manually:

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

## Files to create/modify

- `alembic/versions/<hash>_add_v2_resolution_graph_tables.py` — generated and reviewed migration

## Verification

```bash
make smoke  # requires Docker + PostgreSQL
```

Migration must apply and roll back cleanly without errors.
