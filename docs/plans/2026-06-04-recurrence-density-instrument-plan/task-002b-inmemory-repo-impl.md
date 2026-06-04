# Task 002b (impl): InMemoryQueryEventRepository

**depends-on**: ["002a"]

## Description

Implement `InMemoryQueryEventRepository` so Task 002a's tests pass. This is the reference implementation of the dedup rules and the RD/organic computation; Task 005b mirrors it for SQLAlchemy via a shared helper.

## Execution Context

- **Layer:** infrastructure (`backend/infrastructure/persistence/in_memory.py`).
- **Type:** impl (Green).
- **Prereqs:** 002a (the failing tests this turns green).

## BDD Scenario

```gherkin
Scenario: Recurrence density excludes seed-replay, self-hits, and same-identity replay
  Given an in-memory QueryEvent repository
  When events are added via add_with_dedup
  Then seed-replay and self-hit events are dropped per the exclude flags
  And same identity/IP cluster replays within the window count once
  And recurrence_rollup returns recurrence_density, organic_recurrence,
    total_independent_queries, and per_problem counts

Scenario: An empty or all-seed event log yields a zero, non-crashing rollup
  Given a repository with no events, or only seed-replay events
  When recurrence_rollup is computed
  Then recurrence_density is 0.0 and organic_recurrence is 0.0
  And total_independent_queries is 0
  And no division-by-zero error is raised
```

## Files to Modify/Create

- `backend/infrastructure/persistence/in_memory.py` — add `InMemoryQueryEventRepository` after `InMemoryOutcomeRepository`.

## Steps

Implement the `QueryEventRepository` Protocol over an in-process `list[QueryEvent]`:

1. `add` — append.
2. `add_with_dedup(event, agents, *, exclude_seed_replay, exclude_self_hits, dedup_window_seconds)`:
   - drop (return `False`) if `exclude_seed_replay and event.is_seed_replay`;
   - drop if `exclude_self_hits and event.is_self_hit`;
   - drop if an existing event from the same identity cluster (resolve via `clustering.detect_clusters` on the two agents, or `ip_hash`/`fingerprint_hash` equality when `agent_id` is None) for the same `top_match_problem_id` exists within `dedup_window_seconds`;
   - else append and return `True`.
3. `list_all(since)`, `query_count_for_problem(problem_id, since)`.
4. `recurrence_rollup(*, seed_agent_ids)`:
   - denominator = count of independent (post-dedup, non-seed-replay) events;
   - `recurrence_density` = (events with `top_match_quality in {"exact","strong"}` AND `has_help` AND NOT `is_self_hit`) / denominator, `0.0` if denominator 0;
   - strong-hit set = events with `top_match_quality in {"exact","strong"}` AND `has_help`;
   - `organic_recurrence` = (strong hits whose matched contributor `agent_id` not in `seed_agent_ids` and not a self-hit) / len(strong hits), `0.0` if none;
   - `per_problem` = list of `{problem_id, query_count, organic_recurrence}` sorted by `query_count` desc, top 100;
   - return `{recurrence_density, organic_recurrence, total_independent_queries, per_problem}`.

Reuse `from backend.application.clustering import detect_clusters` for identity grouping — do not invent a new dedup scheme. Use `utc_now()` consistently. The pure metric computation (step 4) should be factored so Task 005b can import the same helper (see 005b) — keep it a module-level function the repo calls.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_query_event_repository.py -q
make fast
```

## Success Criteria

- All Task 002a tests pass **GREEN**.
- `make fast` shows no regression in existing unit tests.
- The metric math is a reusable module function (not inlined in the class) so 005b can share it.
