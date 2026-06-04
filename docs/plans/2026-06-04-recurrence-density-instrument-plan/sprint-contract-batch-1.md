# Sprint Contract — Batch 1

## Scope

Foundation domain contract + the in-memory reference implementation of the recurrence metric. This batch establishes the `QueryEvent` value object, the `QueryEventRepository` Protocol, and `InMemoryQueryEventRepository` with the dedup rules and RD/organic-recurrence computation that the whole instrument (and the SQLAlchemy repo in Batch 2) builds on.

## Tasks

- **#1 / 001** (setup, foundation): `QueryEvent` dataclass + `QueryEventRepository` Protocol — `task-001-domain-queryevent.md`. No Red/Green pair.
- **#2 / 002a** (test, RED): in-memory repo dedup + RD/organic tests — `task-002a-inmemory-repo-test.md`.
- **#3 / 002b** (impl, GREEN): `InMemoryQueryEventRepository` — `task-002b-inmemory-repo-impl.md`.

**Red-Green pair:** #2 (002a) → #3 (002b). 001 must complete before 002a (domain symbols imported by the test).

**Execution order (within batch, sequential by dependency):** 001 → 002a (confirm RED) → 002b (confirm GREEN).

## Acceptance Criteria (from task Then-clauses)

1. `backend/domain/models.py` exports `QueryEvent` (`@dataclass(slots=True)`) with fields: `query_text`, `agent_id`, `ip_hash`, `fingerprint_hash`, `top_match_problem_id`, `top_match_quality`, `has_help`, `is_self_hit`, `is_seed_replay`, `pattern_class_hit`, `event_id`, `created_at`.
2. `backend/domain/repositories.py` exports `QueryEventRepository` Protocol with `add`, `add_with_dedup`, `list_all`, `query_count_for_problem`, `recurrence_rollup`. Domain stays infrastructure-free (import succeeds with no side effects).
3. `InMemoryQueryEventRepository` (`backend/infrastructure/persistence/in_memory.py`):
   - `add_with_dedup` drops seed-replay (when excluded), drops self-hits (when excluded), and collapses same-identity/IP cluster replays within the dedup window to one.
   - `recurrence_rollup` returns `{recurrence_density, organic_recurrence, total_independent_queries, per_problem}`; `recurrence_density` = strong/exact-with-help, non-self, non-seed hits / total independent queries; `organic_recurrence` = strong hits matching a different, non-seed contributor / strong hits; empty/all-seed log → all-zero, no division-by-zero.
   - Reuses `backend.application.clustering.detect_clusters` for identity grouping (no new dedup scheme).
   - The pure metric computation is a reusable module-level function (so Batch 2's SQLAlchemy repo can share it).
4. `backend/tests/unit/test_query_event_repository.py` covers all 7 cases in 002a and passes GREEN after 002b.

## Verification (must all pass, exit 0)

```bash
uv run python -c "from backend.domain.models import QueryEvent; from backend.domain.repositories import QueryEventRepository; print('ok')"
uv run ruff check backend/domain/models.py backend/domain/repositories.py
uv run pytest backend/tests/unit/test_query_event_repository.py -q
make fast
```

## Evaluation Criteria Preview

Assessed against `docs/retros/checklists/code-v2.md`. Emphasis for this batch: domain layer has zero external imports (Clean Architecture); no stub/`pass`-only bodies; dedup reuses `detect_clusters` rather than reinventing; metric math factored as a shared function; tests execute real logic (not `assert True`); `make fast` shows no regression in the existing suite.
