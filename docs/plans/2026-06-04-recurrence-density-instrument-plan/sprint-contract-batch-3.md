# Sprint Contract — Batch 3

## Scope

Persist query events: `QueryEventORM`, `SQLAlchemyQueryEventRepository` (delegating to the shared `compute_recurrence_rollup`), the Alembic migration, and the DB-branch composition-root wiring. Plus the `RUN_DOCKER_TESTS=1`-gated integration test asserting parity with the in-memory repo.

**Environment constraint (hard):** Docker is unavailable and `.env`'s `DATABASE_URL` is **production**. The live integration run is DEFERRED — verify everything offline; do NOT apply the migration or run the smoke test against the configured DATABASE_URL.

## Tasks (Red-Green pair)

- **#8 / 005a** (test, RED, integration): `backend/tests/integration/test_query_event_persistence.py`, `@pytest.mark.smoke`, gated on `RUN_DOCKER_TESTS=1` — `task-005a-persistence-test.md`.
- **#9 / 005b** (impl, GREEN): `QueryEventORM` + `SQLAlchemyQueryEventRepository` + migration + `main.py` DB-branch wiring — `task-005b-persistence-impl.md`.

## Acceptance Criteria

1. `QueryEventORM` (`backend/infrastructure/persistence/sqlalchemy_models.py`, after `OutcomeORM`): `query_events` table, columns mirroring `QueryEvent` (event_id PK; problem_id FK→problems CASCADE nullable index; agent_id FK→agents nullable index; query_text Text; ip_hash/fingerprint_hash String(64); top_match_quality String(10) nullable; has_help/is_self_hit/is_seed_replay/pattern_class_hit Boolean; created_at DateTime(tz) index). No unique constraint; no embedding column.
2. `SQLAlchemyQueryEventRepository` (`sqlalchemy_repositories.py`, after `SQLAlchemyOutcomeRepository`): implements the `QueryEventRepository` Protocol; persistence + loading only; **delegates dedup/rollup to the shared `backend.application._recurrence.compute_recurrence_rollup`** — no reimplemented math.
3. Alembic migration `alembic/versions/t5u6v7w8x9y0_add_query_events_table.py`, `down_revision = "s4t5u6v7w8x9"`; `upgrade` creates the table + indexes on problem_id/agent_id/created_at; `downgrade` drops it. Style matches `s4t5u6v7w8x9_*.py`.
4. `backend/main.py:_build_service` wires `SQLAlchemyQueryEventRepository(session_factory)` into the DB (`database_url` set) branch alongside the other SQLAlchemy repos.
5. The integration test (005a) shares the in-memory test's event fixture and asserts the SQLAlchemy repo's `recurrence_rollup` returns the **same** numbers — parity by shared implementation.

## Verification (OFFLINE only — runnable here)

```bash
uv run ruff check backend/infrastructure/persistence/sqlalchemy_models.py backend/infrastructure/persistence/sqlalchemy_repositories.py backend/main.py backend/tests/integration/test_query_event_persistence.py alembic/versions/t5u6v7w8x9y0_add_query_events_table.py
uv run python -c "import importlib; importlib.import_module('alembic.versions.t5u6v7w8x9y0_add_query_events_table'); print('migration imports')"
DATABASE_URL= uv run alembic history | tail -5   # linear chain, new revision present; do NOT 'upgrade'
DATABASE_URL= uv run pytest backend/tests/integration/test_query_event_persistence.py --collect-only -q   # collects + is skipped without RUN_DOCKER_TESTS
make fast
```

## DEFERRED (do NOT run here — needs Docker/PostgreSQL, must not touch prod DB)

```bash
RUN_DOCKER_TESTS=1 uv run pytest backend/tests/integration/test_query_event_persistence.py -q -m smoke
uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head
```

## Evaluation Criteria Preview

Against `docs/retros/checklists/code-v2.md`. Emphasis: `CODE-MIGRATION` (reversible up/down, correct `down_revision`, matches house style); SQLAlchemy repo delegates to the shared helper (parity, no reimplemented math); ORM column types/constraints correct; `make fast` green; integration test correctly gated + collects; **honest deferral** of the Docker run (no faked GREEN).
