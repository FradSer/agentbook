---
name: migrate
description: Generate and apply an Alembic database migration. Use when domain models or ORM models have changed and the database schema needs updating.
disable-model-invocation: true
---

Run migration for $ARGUMENTS (description of the schema change):

**Step 1 — Verify ORM and domain are in sync.**
Check that `app/infrastructure/persistence/sqlalchemy_models.py` matches `app/domain/models.py`. The `_to_*_domain()` mapper functions in `sqlalchemy_repositories.py` must also map any new fields.

**Step 2 — Generate the migration.**
```bash
uv run alembic revision --autogenerate -m "$ARGUMENTS"
```

**Step 3 — Review the generated file.**
Open the new file in `alembic/versions/`. Confirm:
- `upgrade()` adds columns/tables as expected
- `downgrade()` correctly reverses the change
- No unexpected drops or alterations

**Step 4 — Apply locally.**
```bash
uv run alembic upgrade head
```

**Step 5 — Update AGENTS.md.**
Add the new migration to the migration list in the Database section of AGENTS.md (keep the table in chronological order).

**Step 6 — Run unit tests.**
```bash
make fast
```
Unit tests use in-memory repos and don't hit the DB, but they validate the domain model changes.

> Railway runs `uv run alembic upgrade head` automatically on each API deploy via `preDeployCommand` in `railway.toml`.
