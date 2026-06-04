# Evaluation Report — Code Mode (Round 1, Batch 2)

**Batch:** 2 — service recording hook + `get_recurrence_density` (tasks 003a, 003b)
**Checklist:** `docs/retros/checklists/code-v2.md`
**Branch:** `feat/recurrence-density-instrument`

## Verification (run by evaluator)

| Command | Exit | Result |
|---|---|---|
| `ruff check` (4 batch files) | 0 | All checks passed |
| `pytest test_recurrence_density_service.py test_query_event_repository.py` | 0 | 13 passed |
| `pytest backend/tests/unit` | 0 | 793 passed, 1 skipped (pre-existing, unrelated `test_usage_dashboard.py:424`) |

## Results

All `code-v2` items PASS or N/A (no migration/frontend/formatter-clobber this batch). All sprint-contract acceptance criteria PASS:
- AC1 `query_events` ctor param → `self._query_events`.
- AC2 `search_problems(caller=None)` records one dedup'd event, all flags derived from computed rows.
- AC3 **best-effort**: whole recording body in `try/except` with `logger.exception`; `test_recording_failure_never_breaks_search` proves search returns normally when `query_events` raises.
- AC4 `get_recurrence_density` returns `{recurrence_density, organic_recurrence, total_independent_queries, problems}`; None→all-zero; delegates to `recurrence_rollup(seed_agent_ids=_seed_agent_ids())`; approved-filter; `per_problem`→`problems`.
- AC4b `is_self_hit` = matched reliance-target author == caller agent (anonymous never self-hits); excluded from numerator by the rollup math. No-match → `top_match_problem_id=None`, `has_help=False`.
- AC5 `main.py:_build_service` wires `InMemoryQueryEventRepository` in the `database_url is None` branch; conftest wires it. SQLAlchemy branch correctly deferred to Batch 3.
- AC6 service reimplements no metric math; delegates to repo → shared `compute_recurrence_rollup`.

Red-team (best-effort exception scope, metric-math reimplementation, `is_self_hit` keying, `CallerContext` transport leak) — all FAIL cases refuted.

## Rework Items

None.

## Verdict

**PASS**
