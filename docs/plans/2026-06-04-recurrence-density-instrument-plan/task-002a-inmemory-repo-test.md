# Task 002a (test): In-memory repo dedup + RD/organic computation

**depends-on**: ["001"]

## Description

Write failing unit tests pinning the dedup rules and the RD/organic-recurrence computation against an in-memory `QueryEventRepository`. These tests are the executable contract for the metric semantics; Task 005 (SQLAlchemy) must satisfy the same behavior.

## Execution Context

- **Layer:** unit test (`backend/tests/unit/`), in-memory repos, no Docker (conftest forces `database_url=None`).
- **Type:** test (Red).
- **Prereqs:** 001 (domain `QueryEvent` + Protocol).

## BDD Scenario

Verbatim from the design's `bdd-specs.md` (Recurrence-density gate Feature) — the one code-testable scenario this task anchors:

```gherkin
Scenario: Recurrence density is measured on real traffic, never on the seed set itself
  Given a seeded corpus and a stream of incoming queries
  When recurrence_density is computed
  Then the denominator counts only externally-originated independent queries
  And queries replayed from the seed set are excluded so the metric cannot be self-inflated
  And same-contributor self-hits (querier == matched-entry author) are excluded
```

Derived code-level scenarios (the concrete behaviors that satisfy the above):

```gherkin
Scenario: Dedup rules exclude seed-replay, self-hits, and same-identity replay
  Given a QueryEvent repository
  When events are recorded for a stream of incoming queries
  Then seed-replay events (is_seed_replay=True) are excluded from numerator and denominator
  And self-hit events (is_self_hit=True) are excluded from the numerator
  And self-replay by the same identity/IP cluster within the dedup window counts once
  And recurrence_density = strong/exact-with-help, non-self, non-seed hits / total independent queries
  And organic_recurrence = strong hits matching a different, non-seed contributor / strong hits

Scenario: An empty or all-seed event log yields a zero, non-crashing rollup
  Given a repository with no events, or only seed-replay events
  When recurrence_rollup is computed
  Then recurrence_density is 0.0 and organic_recurrence is 0.0
  And total_independent_queries is 0
  And no division-by-zero error is raised
```

## Files to Modify/Create

- `backend/tests/unit/test_query_event_repository.py` — new unit test file.

## Steps

Write assertions (not implementation) for these cases:

1. `add_with_dedup` returns `False` and records nothing when `is_seed_replay=True` and `exclude_seed_replay=True`.
2. `add_with_dedup` returns `False` for a self-hit when `exclude_self_hits=True`.
3. Two events from the same `ip_hash`/`fingerprint_hash` cluster within `dedup_window_seconds` collapse to one independent query (assert the second is dropped).
4. `recurrence_rollup` over a hand-built event set returns the expected `recurrence_density` (e.g. 3 strong-with-help non-self hits out of 10 independent queries → 0.30).
5. `recurrence_rollup` computes `organic_recurrence` excluding `seed_agent_ids` contributors.
6. Empty log and all-seed-replay log → all-zero rollup, no exception.
7. `query_count_for_problem` counts only non-seed, non-self events for that problem.

Build `QueryEvent` instances directly with explicit flag values; construct `Agent` records via the in-memory agent repo for cluster cases (mirror `_build_service` agent setup in `conftest.py`).

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_query_event_repository.py -q
```

## Success Criteria

- The test file runs and **fails RED** for the right reason: `InMemoryQueryEventRepository` does not yet exist (import/attribute error), not an assertion-logic bug.
- All seven cases are present and target the dedup/exclusion + rollup contract above.
