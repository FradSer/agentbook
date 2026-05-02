# Batch 3 Evaluation — Round 1

**Tasks:** 005a, 005b, 006
**Mode:** Linear (sequential)
**Checklist:** docs/retros/checklists/code-v1.md (v1)

| ID | Result | Evidence |
|---|---|---|
| CODE-ASSUME-01 | PASS | grep'd existing service / fixture names before authoring; confirmed `RESEARCH_TIMEOUT_SECONDS`, `utc_now`, `_research_cycles`, `list_being_researched`, `get_latest_cycle_at` already exist. Verified `freezegun` is NOT a project dep — fell back to manual `utc_now() - timedelta(seconds=N)` pattern, computing snapshot immediately. |
| CODE-ASSUME-02 | PASS | Imports verified: schemas.py already imports `datetime` from `datetime` module and `BaseModel` from `pydantic`; no new imports needed. Service uses existing `utc_now`. Tests import `Agent`, `Problem`, `ResearchCycle` from `backend.domain.models` and the in-memory repos that already exist. |
| CODE-EDIT-01 | PASS | PostToolUse hook reformatted `service.py` after the Edit; no anchor breakage because subsequent action was a test run, not another Edit. Schemas Edit not affected. |
| CODE-EDIT-02 | PASS | Single-pass Edit per file with all symbols already imported; no autoflake stripping observed. |
| CODE-A11Y-01 | N/A | Backend-only batch; no UI. |
| CODE-LINT-01 | PASS | `ruff check backend/application/service.py` and `ruff check backend/presentation/api/schemas.py` both report "All checks passed!" |
| CODE-TEST-01 | PASS | Tests use the autouse `database_url=None` fixture from `backend/tests/conftest.py`; in-memory repos throughout. |
| CODE-TEST-02 | N/A | No integration tests in batch. |
| CODE-TEST-03 | PASS | Red verified: 10 FAILED with `AttributeError: 'AgentbookService' object has no attribute 'get_live_research_snapshot'` — not collection error. |
| CODE-VERIFY-01 | PASS | `make fast` → 445 passed, 3 deselected. Exactly the predicted +10 over the 435 baseline. Zero regressions. |
| CODE-VERIFY-02 | PASS | Service refactor surface verified by the `-k "service"` keyword filter (82 passed, 363 deselected) AND the full fast suite. |
| CODE-SCOPE-01 | PASS | Exactly 3 files touched, all listed in handoff. No frontend touched, no REST handler added, no SSE handler added, no `pyproject.toml` change. |
| CODE-SCOPE-02 | N/A | Coordinator does not commit; parent owns commit. |
| CODE-MIGRATION-01 | N/A | No migration in this batch. |
| CODE-MIGRATION-02 | N/A | No migration in this batch. |

## Quality requirement audit

1. Red phase failed with the *exact* required error (`AttributeError` on `get_live_research_snapshot`). No collection errors.
2. Service composes `list_being_researched(timeout_seconds=RESEARCH_TIMEOUT_SECONDS)` and `get_latest_cycle_at()` only — no re-implemented filtering.
3. Payload allowlist test 7 uses `set(item.keys()) == expected_keys` (strict equality), expected = {problem_id, description, solution_count, best_confidence, research_started_at, elapsed_seconds}. Passing.
4. Service returns ISO 8601 strings for `research_started_at`, `last_cycle_at`, `now`. Pydantic schema in 006 still types them as `datetime` — verified the round-trip probe accepts ISO 8601 string input.
5. Both schemas configured with `model_config = {"extra": "forbid"}`.
6. Determinism: no `freezegun` available; substituted `research_started_at = utc_now() - timedelta(seconds=N)` computed immediately. Edge tests at 359 / 361 / 360±1 s pass deterministically because `list_being_researched` uses the in-memory repo's own `datetime.now(tz=UTC)` snapshot taken in the same wall-clock instant (sub-millisecond delta).
7. No stubs, no `TODO`, no `NotImplementedError` — service body composes real logic.

## Verdict
PASS
