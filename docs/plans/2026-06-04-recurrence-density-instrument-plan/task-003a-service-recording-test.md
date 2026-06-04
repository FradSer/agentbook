# Task 003a (test): Service recording hook + get_recurrence_density

**depends-on**: ["002b"]

## Description

Failing tests that pin (a) `search_problems` records exactly one dedup'd `QueryEvent` per search when a `query_events` repo is wired, and (b) `get_recurrence_density` returns the rollup, with seed-replay and self-hits excluded. Also pin the best-effort guarantee: a recording failure must not fail the search.

## Execution Context

- **Layer:** unit test (`backend/tests/unit/`), in-memory repos.
- **Type:** test (Red).
- **Prereqs:** 002b (the in-memory repo the service records into).

## BDD Scenario

Verbatim from the design's `bdd-specs.md` (the exclusion guarantee this task enforces at the service layer):

```gherkin
Scenario: Recurrence density is measured on real traffic, never on the seed set itself
  Given a seeded corpus and a stream of incoming queries
  When recurrence_density is computed
  Then the denominator counts only externally-originated independent queries
  And queries replayed from the seed set are excluded so the metric cannot be self-inflated
  And same-contributor self-hits (querier == matched-entry author) are excluded
```

Derived code-level scenarios:

```gherkin
Scenario: A search records a query event and the rollup reflects it
  Given a service wired with an in-memory query_events repository
  And a seeded problem authored by agent A with an active solution
  When agent B searches with text that strongly matches that problem
  Then one QueryEvent is recorded with top_match_problem_id set, has_help True, is_self_hit False
  And get_recurrence_density reports recurrence_density > 0 and counts that query

Scenario: A self-hit search is recorded but excluded from recurrence density
  Given a service wired with a query_events repository
  And a problem authored by agent A
  When agent A searches and matches its own problem
  Then the recorded event has is_self_hit True
  And get_recurrence_density does not count it in the numerator

Scenario: Recording never breaks a search
  Given a service whose query_events repository raises on add_with_dedup
  When a search runs
  Then the search still returns its normal payload
  And the recording error is swallowed (best-effort instrumentation)
```

(The "Recording never breaks a search" scenario is an engineering constraint from this plan's `_index.md` Constraints, not a design-Feature scenario.)

## Files to Modify/Create

- `backend/tests/unit/test_recurrence_density_service.py` — new unit test file.
- `backend/tests/conftest.py` — update `_build_service` to wire `InMemoryQueryEventRepository` and expose it via `service._query_events` so tests can assert recorded events.

## Steps

1. After `service.search_problems(...)`, assert `service._query_events.list_all()` has exactly one event with the expected flags (`has_help`, `is_self_hit`, `top_match_quality`).
2. Assert `service.get_recurrence_density()` returns `{"recurrence_density": float, "organic_recurrence": float, "total_independent_queries": int, "problems": [...]}` consistent with recorded events.
3. Self-hit (author searches own problem) → `is_self_hit True`, excluded from `recurrence_density` numerator.
4. A query with no good match records an event with `top_match_problem_id=None`, `has_help=False` (denominator only).
5. Best-effort: inject a stub `query_events` whose `add_with_dedup` raises; assert `search_problems` still returns normally.
6. When `query_events` is `None`, `search_problems` works and `get_recurrence_density` returns the empty rollup.

Create problems/solutions via the service's own write methods so match-quality is realistic.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_recurrence_density_service.py -q
```

## Success Criteria

- Tests **fail RED** for the right reason: `get_recurrence_density` and the recording hook do not exist yet.
- All six cases present, including the best-effort and `query_events is None` cases.
