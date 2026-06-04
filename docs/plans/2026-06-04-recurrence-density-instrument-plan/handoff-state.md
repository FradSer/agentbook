# Handoff State — COMPLETE

**Plan:** Recurrence-Density Instrument (`docs/plans/2026-06-04-recurrence-density-instrument-plan/`)
**Branch:** `feat/recurrence-density-instrument`

## Batch progress — ALL DONE

- **Batch 1** (001, 002a, 002b — domain + in-memory repo): DONE, PASS (`evaluation-round-1-batch-1.md`).
- **Batch 2** (003a, 003b — service hook + rollup): DONE, PASS (`evaluation-round-1-batch-2.md`).
- **Batch 3** (005a, 005b — SQLAlchemy persistence + migration): DONE, PASS (`evaluation-round-1-batch-3.md`). Live Docker run DEFERRED (no Docker; prod DATABASE_URL).
- **Batch 4** (004a, 004b MCP + 006a, 006b dashboard): DONE, PASS (`evaluation-round-1-batch-4.md`).

## Completed task IDs

ALL 11: #1-#11 (001, 002a, 002b, 003a, 003b, 004a, 004b, 005a, 005b, 006a, 006b).

## Final test state

`make fast`: **802 passed, 1 skipped, 0 failed** (the skip is pre-existing, unrelated to this work).

## Full modified/created file set (for the Phase 5 commit)

Source:
- `backend/domain/models.py` (+ `QueryEvent`)
- `backend/domain/repositories.py` (+ `QueryEventRepository`)
- `backend/application/_recurrence.py` (NEW — `compute_recurrence_rollup`)
- `backend/application/service.py` (+ `CallerContext`, `query_events` ctor, recording hook, `get_recurrence_density`, `_seed_agent_ids`, `_is_self_hit`, `_record_query_event`)
- `backend/infrastructure/persistence/in_memory.py` (+ `InMemoryQueryEventRepository`)
- `backend/infrastructure/persistence/sqlalchemy_models.py` (+ `QueryEventORM`)
- `backend/infrastructure/persistence/sqlalchemy_repositories.py` (+ `SQLAlchemyQueryEventRepository`)
- `backend/main.py` (`_build_service` wires both repo branches)
- `alembic/versions/t5u6v7w8x9y0_add_query_events_table.py` (NEW migration)
- `backend/presentation/mcp/tools.py` (recall `caller=` wiring + `hash_remote_addr`)
- `backend/presentation/api/schemas.py` (+ recurrence-density response models)
- `backend/presentation/api/routes/dashboard.py` (+ `/recurrence-density` endpoint)

Tests:
- `backend/tests/unit/test_query_event_repository.py` (NEW)
- `backend/tests/unit/test_recurrence_density_service.py` (NEW)
- `backend/tests/unit/test_mcp_recall_recurrence.py` (NEW)
- `backend/tests/unit/test_dashboard_recurrence_endpoint.py` (NEW)
- `backend/tests/integration/test_query_event_persistence.py` (NEW, Docker-gated)
- `backend/tests/conftest.py` (`_build_service` wires `InMemoryQueryEventRepository`)
- `backend/tests/unit/test_mcp_dispatch.py`, `backend/tests/unit/test_mcp_search_public.py` (updated recall-signature assertions for `caller=`)

Plan process docs: `sprint-contract-batch-{1..4}.md`, `evaluation-round-1-batch-{1..4}.md`, `handoff-state.md`.

## DEFERRED (post-merge, needs Docker/PostgreSQL — must not run against prod)

- `RUN_DOCKER_TESTS=1 uv run pytest backend/tests/integration/test_query_event_persistence.py -m smoke`
- `uv run alembic upgrade head` (apply the `query_events` migration on a real DB) + downgrade round-trip.
