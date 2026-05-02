# Batch 4 Evaluation — Round 1

**Tasks:** 007a, 007b, 010
**Mode:** REST pair (sequential) + frontend types (parallel)
**Checklist:** docs/retros/checklists/code-v1.md (v1)

| ID | Result | Evidence |
|---|---|---|
| CODE-ASSUME-01 | PASS | Grepped `dynamic_search_limit`/`limiter` in `backend/core/rate_limit.py` and `enable_limiter`/`_build_client` patterns in existing dashboard tests before authoring. |
| CODE-ASSUME-02 | PASS | Verified `get_optional_current_agent` exists in `deps.py:36-55`; `Agent` import from `domain.models`. |
| CODE-EDIT-01 | PASS (with rework) | Autoflake stripped `Agent` + `get_optional_current_agent` imports after the route only referenced them in a single-line annotation. Re-Read + re-added together with explicit usage; second pass survived. |
| CODE-EDIT-02 | PASS | Imports added in same Edit pass as the type-annotation usage; second autoflake pass kept them. |
| CODE-A11Y-01 | N/A | No UI element in this batch (only types). |
| CODE-LINT-01 | PASS | `ruff check backend/presentation/api/routes/dashboard.py` clean; `pnpm lint` (biome + tsc) clean. |
| CODE-TEST-01 | PASS | Tests use autouse `database_url=None` fixture (in-memory). |
| CODE-TEST-02 | N/A | No integration tests in batch. |
| CODE-TEST-03 | PASS | 007a Red was 404 Not Found (route missing), exact intended failure mode. After 007b Green, all 8 PASSED. |
| CODE-VERIFY-01 | PASS | `make fast`: 453 passed, 3 deselected. Exactly +8 over the 445 baseline; 0 regressions. |
| CODE-VERIFY-02 | PASS | Touched shared infra (`dashboard.py` route registration) — full unit suite re-run succeeded. |
| CODE-SCOPE-01 | PASS | Only `test_dashboard_live_routes.py`, `dashboard.py`, `frontend/lib/types.ts`, `frontend/lib/api.ts` modified — all listed in task files. |
| CODE-SCOPE-02 | N/A | Parent agent owns commit. |
| CODE-MIGRATION-01 | N/A | No migration. |
| CODE-MIGRATION-02 | N/A | No migration. |

## Observations

- **Authenticated rate-limit tier required `get_optional_current_agent` Depends on the route.** The initial implementation by the previous coordinator omitted this dep; the 300/min auth test failed (caller fell back to anonymous 30/min IP keying). Adding the optional auth dep populates `request.state.agent`, which the rate-limit `_rate_key` reads. Worth recording as a CODE-ASSUME-style learning for any future endpoint using `dynamic_search_limit`.
- **Autoflake hook stripped imports added but unused at first.** Repeating the batch-2 lesson: when adding an import that's only consumed in a function annotation/default, autoflake may consider it unused if the formatter runs before the body line referencing it lands. Mitigation: add the import + usage in a single Edit pass, then re-Read after PostToolUse if any subsequent Edit will target the same region.

## Verdict

PASS — 8/8 dashboard tests pass, 453/453 unit tests pass (0 regressions), frontend tsc + biome clean. No rework items.
