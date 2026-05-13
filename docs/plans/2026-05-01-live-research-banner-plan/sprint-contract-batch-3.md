# Sprint Contract — Batch 3 (Service Snapshot + Schemas)

**Plan:** `docs/plans/2026-05-01-live-research-banner-plan/`
**Batch:** 3 of 7
**Mode:** Linear (sequential dependency chain 005a → 005b → 006)
**Code checklist:** `docs/retros/checklists/code-v1.md` (v1)

## Tasks in this batch

| Plan ID | TaskList ID | Subject | Depends-on |
|---|---|---|---|
| 005a | 6 | service.get_live_research_snapshot() — Red | 004b ✓ |
| 005b | 7 | service.get_live_research_snapshot() — Green | 005a |
| 006 | 8 | LiveResearchSnapshotResponse + LiveResearchActiveItem schemas | 005b |

## Acceptance Criteria (auto-derived from task files)

### Task 005a — Service tests (Red)
- File `backend/tests/unit/test_service_live_research.py` created with 10 test contracts:
  1. empty state → `{"active": [], "last_cycle_at": None, "now": <iso>}`
  2. single active problem → 1 item with all required keys
  3. ordering by `research_started_at` DESC (3 problems)
  4. excludes row at 361 s (window edge)
  5. includes row at 359 s (window edge)
  6. returns global MAX(`research_cycles.created_at`) for `last_cycle_at`
  7. payload allowlist exactly: problem_id, description, solution_count, best_confidence, research_started_at, elapsed_seconds (NO agent_id/reporter/email/markdown)
  8. truncates `description` to 300 chars (500-char input → 300-char output)
  9. `research_started_at` and `now` serialised as ISO 8601 strings (not `datetime`)
  10. uses `RESEARCH_TIMEOUT_SECONDS` from service module
- All 10 tests FAIL with `AttributeError: 'AgentbookService' object has no attribute 'get_live_research_snapshot'`.
- Tests use the autouse `database_url=None` fixture (in-memory repos via `conftest.py`).
- Use `freezegun` (already a project dep — verify via grep) OR a clock-fixture pattern present in the existing service tests for deterministic 359/361 s assertions.
- No production code modified.

### Task 005b — Service impl (Green)
- `AgentbookService.get_live_research_snapshot(self) -> dict` added to `backend/application/service.py`.
- Calls `self._problems.list_being_researched(timeout_seconds=RESEARCH_TIMEOUT_SECONDS)`.
- Calls `self._research_cycles.get_latest_cycle_at()` guarded by `if self._research_cycles is not None`.
- Truncates `description` to 300 chars per active item.
- `elapsed_seconds = int((now - p.research_started_at).total_seconds())`.
- Order: matches repo's DESC (already DESC from 004b).
- ISO 8601 serialisation: `research_started_at`, `last_cycle_at`, `now` are strings (use `.isoformat()`).
- NO `author_id`, `reporter_id`, agent emails, solution markdown bodies in payload.
- 10/10 tests in `test_service_live_research.py` PASS.
- All existing `service` keyword tests still pass.
- `uv run ruff check backend/application/service.py` exits 0.

### Task 006 — Pydantic schemas
- Two new classes in `backend/presentation/api/schemas.py`:
  - `LiveResearchActiveItem`: problem_id (str), description (str), solution_count (int), best_confidence (float), research_started_at (datetime), elapsed_seconds (int)
  - `LiveResearchSnapshotResponse`: active (list), last_cycle_at (datetime | None), now (datetime)
- Both configured with `model_config = {"extra": "forbid"}`.
- Style matches existing dashboard envelopes (`RadarApiResponse`, `ResearchCandidatesResponse`).
- Verification probe round-trips:
  - import: `from backend.presentation.api.schemas import LiveResearchSnapshotResponse, LiveResearchActiveItem`
  - construct + `.model_dump_json()` succeeds
- `uv run ruff check backend/presentation/api/schemas.py` exits 0.

## Code checklist v1 — items most relevant this batch

- **CODE-ASSUME-01 / 02**: grep for existing schema class style + `model_config` patterns in `schemas.py` BEFORE writing 006. Confirm `freezegun` is available (`grep freezegun pyproject.toml uv.lock` or look at existing tests using it).
- **CODE-EDIT-01 / 02**: re-Read `service.py` and `schemas.py` after `ruff format` runs.
- **CODE-LINT-01**: `uv run ruff check` on touched files at end of each task.
- **CODE-VERIFY-01**: `make fast` after each green task — expect 435 → 445 passing (10 new service tests).
- **CODE-TEST-01**: in-memory repos, no DB.
- **CODE-TEST-03**: 005a Red must FAIL with the exact `AttributeError` on `get_live_research_snapshot`, not collection error.
- **CODE-SCOPE-01**: 005a touches `test_service_live_research.py` only; 005b touches `service.py` only; 006 touches `schemas.py` only.

## Out-of-scope guards

- Do NOT add the REST endpoint `/v1/dashboard/research/live` in this batch — that's Task 007.
- Do NOT touch any frontend file.
- Do NOT add a new dependency to `pyproject.toml`.
- Do NOT refactor existing service methods.
- The Pydantic schemas in 006 must use `extra='forbid'` so service-side typos surface as validation errors at the REST handler boundary.

## Verification commands (per task)

### Task 005a
```bash
uv run pytest backend/tests/unit/test_service_live_research.py -x
# Expected: 10 FAILED tests, AttributeError on missing method
```

### Task 005b
```bash
uv run pytest backend/tests/unit/test_service_live_research.py -x
# Expected: 10 PASSED
uv run pytest backend/tests/unit -k "service" -x
# Expected: all PASS (no regression in existing service tests)
uv run ruff check backend/application/service.py
```

### Task 006
```bash
uv run python -c "from backend.presentation.api.schemas import LiveResearchSnapshotResponse, LiveResearchActiveItem"
uv run python -c "
from backend.presentation.api.schemas import LiveResearchSnapshotResponse, LiveResearchActiveItem
from datetime import datetime, timezone
item = LiveResearchActiveItem(problem_id='abc', description='x', solution_count=1, best_confidence=0.5, research_started_at=datetime.now(timezone.utc), elapsed_seconds=10)
resp = LiveResearchSnapshotResponse(active=[item], last_cycle_at=None, now=datetime.now(timezone.utc))
print(resp.model_dump_json())
"
uv run ruff check backend/presentation/api/schemas.py
```

### Full-batch regression (CODE-VERIFY-01)
```bash
make fast
# Expected: 445 passed, 3 deselected (435 baseline + 10 new service tests)
```
