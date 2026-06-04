# Task 005a (test): SQLAlchemy repo + ORM + migration integration

**depends-on**: ["002b"]

## Description

Failing integration test that `SQLAlchemyQueryEventRepository` persists query events to the `query_events` table and computes the **same** dedup/rollup semantics as the in-memory repo (Task 002). Pins parity so the DB path cannot silently diverge.

## Execution Context

- **Layer:** integration test (`backend/tests/integration/`), `@pytest.mark.smoke`, gated on `RUN_DOCKER_TESTS=1` (real PostgreSQL).
- **Type:** test (Red, integration).
- **Prereqs:** 002b (the in-memory repo + shared metric helper this asserts parity against).

## BDD Scenario

Verbatim from the design's `bdd-specs.md` (the exclusion guarantee, here enforced on the DB path):

```gherkin
Scenario: Recurrence density is measured on real traffic, never on the seed set itself
  Given a seeded corpus and a stream of incoming queries
  When recurrence_density is computed
  Then the denominator counts only externally-originated independent queries
  And queries replayed from the seed set are excluded so the metric cannot be self-inflated
  And same-contributor self-hits (querier == matched-entry author) are excluded
```

Derived code-level scenario:

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

- `backend/tests/integration/test_query_event_persistence.py` — new integration test, marked `@pytest.mark.smoke`, gated on `RUN_DOCKER_TESTS=1`.

## Steps

1. After `alembic upgrade head`, assert the `query_events` table exists with expected columns and indexes (`problem_id`, `agent_id`, `created_at`).
2. Record the identical event fixture from Task 002a through `SQLAlchemyQueryEventRepository.add_with_dedup`; assert `recurrence_rollup` returns the **same** numbers as `InMemoryQueryEventRepository` on that fixture (share the fixture builder).
3. FK integrity: an event with a real `problem_id`/`agent_id` persists; `ON DELETE CASCADE` removes events when the problem is deleted.
4. `list_all(since=...)` and `query_count_for_problem` return correct windowed counts from the DB.

Follow the existing integration-test pattern in `backend/tests/integration/` (Docker Postgres fixture).

## Verification Commands

```bash
RUN_DOCKER_TESTS=1 uv run pytest backend/tests/integration/test_query_event_persistence.py -q -m smoke
```

## Success Criteria

- Test **fails RED** for the right reason: ORM model, repo, and migration do not exist yet.
- The parity assertion compares DB-repo output against in-memory-repo output on a shared fixture.
