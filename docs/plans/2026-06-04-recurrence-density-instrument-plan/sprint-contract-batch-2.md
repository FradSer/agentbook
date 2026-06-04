# Sprint Contract — Batch 2

## Scope

Wire the recurrence instrument into the application layer: `AgentbookService` records a dedup'd `QueryEvent` on the read path (`search_problems`) and exposes `get_recurrence_density`. Pure unit scope (in-memory repos) — no DB, fully verifiable via pytest + `make fast`.

## Tasks (Red-Green pair)

- **#4 / 003a** (test, RED): service recording hook + `get_recurrence_density` tests — `task-003a-service-recording-test.md`.
- **#5 / 003b** (impl, GREEN): constructor wiring + recording hook + `get_recurrence_density` + `main.py` in-memory wiring — `task-003b-service-recording-impl.md`.

**Execution:** Red-Green — write 003a tests, confirm RED, implement 003b to GREEN.

## Acceptance Criteria (from task Then-clauses)

1. `AgentbookService.__init__` accepts `query_events: QueryEventRepository | None = None` → `self._query_events`.
2. `search_problems` records exactly one `QueryEvent` per search via `self._query_events.add_with_dedup(...)`, deriving `top_match_problem_id`, `top_match_quality`, `has_help`, `is_self_hit`, `pattern_class_hit` from the computed rows; accepts an optional `caller: CallerContext | None = None` param (default None) for identity enrichment.
3. **Best-effort:** a recording exception is swallowed (and logged) — `search_problems` still returns its normal payload. A stub `query_events` that raises does not break search.
4. `get_recurrence_density()` returns `{"recurrence_density", "organic_recurrence", "total_independent_queries", "problems"}`; returns the all-zero/empty rollup when `self._query_events is None`; delegates to `recurrence_rollup(seed_agent_ids=self._seed_agent_ids())` (seed set starts with the reserved `SANDBOX_AGENT_ID`), filters to approved problems, renames `per_problem`→`problems`.
4. Self-hit search → `is_self_hit True`, excluded from the `recurrence_density` numerator. No-good-match search → `top_match_problem_id=None`, `has_help=False` (denominator only).
5. `backend/main.py:_build_service` wires `InMemoryQueryEventRepository` in the `database_url is None` branch. `conftest.py:_build_service` wires it so tests can assert `service._query_events`.
6. Service does NOT reimplement metric math — it delegates to the repo's `recurrence_rollup` (which uses the shared `compute_recurrence_rollup`).

## Verification (must pass, exit 0)

```bash
uv run ruff check backend/application/service.py backend/main.py backend/tests/unit/test_recurrence_density_service.py
uv run pytest backend/tests/unit/test_recurrence_density_service.py -q
make fast
```

## Evaluation Criteria Preview

Against `docs/retros/checklists/code-v2.md`. Emphasis: best-effort recording (no exception escapes `search_problems`); service orchestrates but does not reimplement metric math; Clean Architecture (presentation/identity enrichment deferred to Batch 4, service stays the orchestrator); `CallerContext` is a small carrier, not a leak of presentation concerns; no stubs; tests execute real logic; full suite green.
