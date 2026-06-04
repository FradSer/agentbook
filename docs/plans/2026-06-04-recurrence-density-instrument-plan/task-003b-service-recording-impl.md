# Task 003b (impl): Service recording hook + get_recurrence_density

**depends-on**: ["003a"]

## Description

Wire the `query_events` repository into `AgentbookService`, record a dedup'd event on the read path, and expose `get_recurrence_density`. Make Task 003a's tests pass.

## Execution Context

- **Layer:** application (`backend/application/service.py`) + composition root (`backend/main.py`, in-memory branch).
- **Type:** impl (Green).
- **Prereqs:** 003a.

## BDD Scenario

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

## Files to Modify/Create

- `backend/application/service.py` — constructor param + recording hook in `search_problems` + new `get_recurrence_density`.
- `backend/main.py` — `_build_service` wires `InMemoryQueryEventRepository` when `database_url is None` (SQLAlchemy wiring lands in Task 005b).

## Steps

1. **Constructor** (`AgentbookService.__init__`, ~line 372): add `query_events: QueryEventRepository | None = None`; assign `self._query_events = query_events`.
2. **Recording hook** in `search_problems` (after `self._search_cache.set(...)`, before `return payload`, ~line 567):
   - skip if `self._query_events is None`;
   - derive from the already-computed `rows`/`payload`: top match `problem_id`, `top_match_quality`, `has_help` (reliance target present), `is_self_hit` (top match contributor `author_id == caller_agent_id` when known), `pattern_class_hit`;
   - build a `QueryEvent` and call `self._query_events.add_with_dedup(event, self._agents, ...)`;
   - wrap in a narrow `try/except` that swallows and logs — recording must never fail the search.
   - Add an optional caller-context parameter to `search_problems` (e.g. `caller: CallerContext | None = None`) defaulted to `None` so existing callers are unaffected; the MCP/REST layer enriches `agent_id`/`ip_hash` (Task 004). **Intent only** signature sketch:

     ```python
     # Intent only — signature, not body
     def search_problems(self, query, limit, error_log=None, include=None,
                         format="concise", pattern_class=None,
                         caller: "CallerContext | None" = None) -> dict: ...
     ```

3. **`get_recurrence_density`** (new method, after `get_usage_dashboard`, ~line 2260):
   - return the empty rollup `{"recurrence_density": 0.0, "organic_recurrence": 0.0, "total_independent_queries": 0, "problems": []}` when `self._query_events is None`;
   - else call `self._query_events.recurrence_rollup(seed_agent_ids=self._seed_agent_ids())`, rename `per_problem` → `problems`, filter to approved problems.
   - `_seed_agent_ids()` helper returns the configured seed/operator identity set (start with the reserved `SANDBOX_AGENT_ID`; one private method, single source).

Do not reimplement the metric math here — it lives in the repo helper (Task 002b). The service only orchestrates and shapes the response.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_recurrence_density_service.py backend/tests/unit/test_query_event_repository.py -q
make fast
```

## Success Criteria

- Task 003a tests pass **GREEN**; 002 tests stay green.
- `make fast` shows no regression.
- A recording exception never propagates out of `search_problems`.
