# Task 005b (impl): QueryEventORM + SQLAlchemyQueryEventRepository + Alembic migration

**depends-on**: ["005a", "001", "002b"]

## Description

Persist query events: ORM model, SQLAlchemy repository (mirroring in-memory dedup/rollup semantics via the shared metric helper), and the Alembic migration. Make Task 005a's integration test pass. Depends on `002b` because the parity mandate requires refactoring the metric math out of the in-memory repo into a shared helper both repos import — that refactor cannot precede `002b` and must keep 002's tests green.

## Execution Context

- **Layer:** infrastructure (`sqlalchemy_models.py`, `sqlalchemy_repositories.py`, `alembic/versions/`) + composition root (`backend/main.py`, DB branch).
- **Type:** impl (Green).
- **Prereqs:** 005a (failing integration test), 001 (domain), 002b (in-memory reference + shared helper).

## BDD Scenario

```gherkin
Scenario: The SQLAlchemy query-event repo matches in-memory semantics on a real database
  Given a PostgreSQL database migrated to head
  And a SQLAlchemyQueryEventRepository
  When the same event sequence used in the in-memory test is recorded via add_with_dedup
  Then seed-replay and self-hits are excluded identically
  And same-identity replays within the window collapse identically
  And recurrence_rollup returns the same recurrence_density and organic_recurrence as the in-memory repo
  And the query_events table persists the non-dropped events with their FKs intact
```

## Files to Modify/Create

- `backend/infrastructure/persistence/sqlalchemy_models.py` — add `QueryEventORM` after `OutcomeORM`.
- `backend/infrastructure/persistence/sqlalchemy_repositories.py` — add `SQLAlchemyQueryEventRepository` after `SQLAlchemyOutcomeRepository`.
- `alembic/versions/t5u6v7w8x9y0_add_query_events_table.py` — new migration, `down_revision = "s4t5u6v7w8x9"` (current head: `add_root_cause_class_to_solutions`).
- `backend/main.py` — `_build_service` wires `SQLAlchemyQueryEventRepository` when `database_url` is set (the in-memory branch was wired in Task 003b).
- `backend/application/_recurrence.py` (or equivalent module) — the shared metric-math helper extracted from `InMemoryQueryEventRepository` (Task 002b), imported by both repos.

## Steps

1. **`QueryEventORM`** (`__tablename__ = "query_events"`), columns mirroring `QueryEvent`. **Intent only:**

   ```python
   # Intent only — column contract, match house ORM style
   class QueryEventORM(Base):
       __tablename__ = "query_events"
       event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
       problem_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("problems.problem_id", ondelete="CASCADE"), nullable=True, index=True)
       agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agents.agent_id"), nullable=True, index=True)
       query_text: Mapped[str] = mapped_column(Text, nullable=False)
       ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
       fingerprint_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
       top_match_quality: Mapped[str | None] = mapped_column(String(10), nullable=True)
       has_help: Mapped[bool] = mapped_column(Boolean, nullable=False)
       is_self_hit: Mapped[bool] = mapped_column(Boolean, nullable=False)
       is_seed_replay: Mapped[bool] = mapped_column(Boolean, nullable=False)
       pattern_class_hit: Mapped[bool] = mapped_column(Boolean, server_default="0", nullable=False)
       created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
   ```
   No embedding column (FlexibleVector N/A). No unique constraint — append-only.

2. **Extract the shared helper:** move the pure metric computation from `InMemoryQueryEventRepository` (002b) into a module function; have both repos call it. This is the structural guarantee of parity — 005a's test asserts equal numbers, this refactor makes them share one implementation. Re-run 002's tests to confirm they stay green after the extraction.

3. **`SQLAlchemyQueryEventRepository`** — implement the Protocol; persistence + loading only, delegating dedup/rollup to the shared helper.

4. **Migration** — `op.create_table("query_events", ...)` with the columns above and indexes on `problem_id`, `agent_id`, `created_at`; `downgrade` drops the table. Match the style of `alembic/versions/s4t5u6v7w8x9_*.py`.

5. **Composition root** — in `backend/main.py:_build_service`, add `query_events=SQLAlchemyQueryEventRepository(session_factory)` to the DB branch alongside the other SQLAlchemy repos.

## Verification Commands

```bash
RUN_DOCKER_TESTS=1 uv run pytest backend/tests/integration/test_query_event_persistence.py -q -m smoke
uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head
make fast
```

## Success Criteria

- Task 005a integration test passes **GREEN**; migration is reversible.
- The shared-helper extraction keeps Task 002a's in-memory tests **green** (`make fast` clean).
- DB-repo and in-memory-repo produce identical rollups on the shared fixture (parity by shared implementation, not coincidence).
