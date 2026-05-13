# Sprint Contract — Batch 2 (Repo + SSE Concurrency Red/Green)

**Plan:** `docs/plans/2026-05-01-live-research-banner-plan/`
**Batch:** 2 of 7
**Mode:** Two parallel Red/Green pairs (independent file sets)
**Code checklist:** `docs/retros/checklists/code-v1.md` (v1)

## Tasks in this batch

| Plan ID | TaskList ID | Subject | Depends-on |
|---|---|---|---|
| 004a | 4 | Repository methods (in-memory + SQLAlchemy) — Red | 002 ✓ |
| 004b | 5 | Repository methods (in-memory + SQLAlchemy) — Green | 004a, 003 ✓ |
| 008a | 11 | core/sse_concurrency.py per-IP semaphore — Red | 002 ✓ |
| 008b | 12 | core/sse_concurrency.py per-IP semaphore — Green | 008a |

## Execution mode

The two Red/Green pairs operate on **disjoint** file sets:
- **Pair 004**: `backend/tests/unit/test_in_memory_repos.py`, `backend/tests/integration/test_sqlalchemy_repos.py`, `backend/infrastructure/persistence/in_memory.py`, `backend/infrastructure/persistence/sqlalchemy_repositories.py`
- **Pair 008**: `backend/tests/unit/test_sse_concurrency.py`, `backend/core/sse_concurrency.py`

The pairs can be executed in either order; within each pair Red→Green is strict.

## Acceptance Criteria (auto-derived from task files)

### Task 004a — Repository tests (Red)
- 5 unit tests added in `backend/tests/unit/test_in_memory_repos.py` covering: 360s window inclusion/exclusion (359/361/NULL), DESC ordering, empty active set, `get_latest_cycle_at` empty, `get_latest_cycle_at` MAX.
- 5 integration tests added in `backend/tests/integration/test_sqlalchemy_repos.py` covering the same contracts, marked `@pytest.mark.smoke`.
- All 10 tests must FAIL with `AttributeError: '...Repository' object has no attribute 'list_being_researched'` (or `get_latest_cycle_at`).
- Tests use existing fixtures (in-memory repo / Postgres `db_session` from the file). No fixture rewrites.
- No production code modified in this task.

### Task 004b — Repository impl (Green)
- `InMemoryProblemRepository.list_being_researched(timeout_seconds: int = RESEARCH_TIMEOUT_SECONDS) -> list[Problem]` — filter by non-null + freshness, order DESC.
- `InMemoryResearchCycleRepository.get_latest_cycle_at() -> datetime | None` — MAX(created_at) or None.
- `SQLAlchemyProblemRepository.list_being_researched(...)` — uses `func.now() - func.make_interval(secs=timeout_seconds)` server-side (NOT Python `datetime.utcnow()` client-side).
- `SQLAlchemyResearchCycleRepository.get_latest_cycle_at()` — `SELECT MAX(created_at) FROM research_cycles`.
- 5/5 in-memory tests PASS.
- If Docker/Postgres available: 5/5 integration tests PASS via `RUN_DOCKER_TESTS=1 uv run pytest backend/tests/integration/test_sqlalchemy_repos.py -k "list_being_researched or get_latest_cycle_at" -x`. Otherwise document and proceed.
- `uv run ruff check backend/infrastructure/persistence/` exits 0.

### Task 008a — sse_concurrency tests (Red)
- 7 tests added in `backend/tests/unit/test_sse_concurrency.py` covering: acquire under cap, raise at cap, release decrements, authenticated cap=20, total worker cap=200, lock contention via `asyncio.gather`, `try/finally` decrement on exception.
- All 7 tests must FAIL with `ModuleNotFoundError: No module named 'backend.core.sse_concurrency'`.
- Uses `pytest-asyncio` markers consistent with repo convention.
- No production code created.

### Task 008b — sse_concurrency impl (Green)
- `backend/core/sse_concurrency.py` exports: `SSEConcurrencyLimiter`, `TooManyConcurrentStreams`, `limiter` (singleton), `ANONYMOUS_CONCURRENCY_CAP=5`, `AUTHENTICATED_CONCURRENCY_CAP=20`, `WORKER_TOTAL_CAP=200`.
- Acquire/release O(1) under a single `asyncio.Lock`.
- `acquire(key, *, authenticated=False)` is an `@asynccontextmanager`.
- `acquire` raises `TooManyConcurrentStreams` BEFORE incrementing if either per-key or per-worker cap would be exceeded.
- `try/finally` decrement under the same lock — exception in body still decrements.
- 7/7 tests in `test_sse_concurrency.py` PASS.
- `uv run ruff check backend/core/sse_concurrency.py` exits 0.
- Module import probe passes: `python -c "from backend.core.sse_concurrency import limiter, SSEConcurrencyLimiter, TooManyConcurrentStreams"`.

## Code checklist v1 — items most relevant this batch

- **CODE-ASSUME-01 / 02**: grep for `class InMemoryProblemRepository`, `class SQLAlchemyProblemRepository`, the existing test fixtures (`db_session`, factory helpers) BEFORE writing tests/imports.
- **CODE-EDIT-01 / 02**: re-Read after `ruff format` runs. Pair 004's two impl files are touched by ruff; Edit anchors must come from post-format content.
- **CODE-LINT-01**: every task concludes with `uv run ruff check` on touched files.
- **CODE-VERIFY-01**: full unit-suite regression must pass before marking each task complete (`make fast`).
- **CODE-TEST-01**: unit tests use in-memory repos only.
- **CODE-TEST-02**: integration suite gated behind `RUN_DOCKER_TESTS=1`.
- **CODE-TEST-03**: Red tests must fail for the intended reason — `AttributeError` for 004a, `ModuleNotFoundError` for 008a.
- **CODE-SCOPE-01**: stay within listed files. The 004 pair must not modify `service.py` or `repositories.py`. The 008 pair must not modify any persistence layer.

## Out-of-scope guards

- Do NOT create the SSE route handler in this batch — that lands in 009b.
- Do NOT call `limiter.acquire(...)` from any production code — wiring lands in 009b.
- Do NOT modify `backend/main.py`, `backend/presentation/api/`, or any frontend file in this batch.
- Do NOT add a new dependency to `pyproject.toml`.
- The 004b SQLAlchemy filter MUST run server-side (`func.now()` + `func.make_interval`), not client-side. Client-side time math creates skew when multiple workers poll simultaneously.

## Verification commands (per task)

### Task 004a
```bash
uv run pytest backend/tests/unit/test_in_memory_repos.py -k "list_being_researched or get_latest_cycle_at" -x
# Expected: 5 FAILED tests, AttributeError
RUN_DOCKER_TESTS=1 uv run pytest backend/tests/integration/test_sqlalchemy_repos.py -k "list_being_researched or get_latest_cycle_at" -x
# Expected: 5 FAILED tests (if Docker available; otherwise skipped — document)
```

### Task 004b
```bash
uv run pytest backend/tests/unit/test_in_memory_repos.py -k "list_being_researched or get_latest_cycle_at" -x
# Expected: 5 PASSED
RUN_DOCKER_TESTS=1 uv run pytest backend/tests/integration/test_sqlalchemy_repos.py -k "list_being_researched or get_latest_cycle_at" -x
# Expected: 5 PASSED (if Docker available)
uv run ruff check backend/infrastructure/persistence/
```

### Task 008a
```bash
uv run pytest backend/tests/unit/test_sse_concurrency.py -x
# Expected: 7 FAILED tests, ModuleNotFoundError
```

### Task 008b
```bash
uv run pytest backend/tests/unit/test_sse_concurrency.py -x
# Expected: 7 PASSED
uv run python -c "from backend.core.sse_concurrency import limiter, SSEConcurrencyLimiter, TooManyConcurrentStreams"
uv run ruff check backend/core/sse_concurrency.py
```

### Full-batch regression (CODE-VERIFY-01)
```bash
make fast
# Expected: 423 + 5 + 7 = 435 passed, no regressions
```
