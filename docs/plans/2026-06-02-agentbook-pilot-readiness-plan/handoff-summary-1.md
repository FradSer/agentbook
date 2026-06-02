# Handoff Summary — Batch 1

## Completed Tasks

| ID | Subject | Checklist Result | Batch |
|----|---------|------------------|-------|
| 001 | Shared cross-transport contract test harness | PASS (all items) | 1 |
| 002-test | transport-read-parity — Test (Red) | PASS (all items) | 1 |
| 002-impl | transport-read-parity — Impl (Green) | PASS (all items) | 1 |

## Remaining Tasks

| ID | Subject | Status | Dependencies |
|----|---------|--------|--------------|
| 003-test | contribute-no-silent-failure — Test | pending | 001 |
| 003-impl | contribute-no-silent-failure — Impl | pending | 003-test |
| 004-test | write-dedup — Test | pending | 001 |
| 004-impl | write-dedup — Impl | pending | 004-test |
| 005-test | honest-match-labeling — Test | pending | 001 |
| 005-impl | honest-match-labeling — Impl | pending | 005-test |
| 006-test | recall-latency — Test | pending | 001 |
| 006-impl | recall-latency — Impl | pending | 006-test |
| 007-test | misconfig-fail-loud — Test | pending | 001 |
| 007-impl | misconfig-fail-loud — Impl | pending | 007-test |
| 008-test | mcp-error-contract — Test | pending | 001 |
| 008-impl | mcp-error-contract — Impl | pending | 008-test |
| 009-test | rejection-signaling-parity — Test | pending | 001 |
| 009-impl | rejection-signaling-parity — Impl | pending | 009-test |
| 010-test | reliance-target — Test | pending | 001 |
| 010-impl | reliance-target — Impl | pending | 010-test, 002-impl |
| 011-test | outcome-summary — Test | pending | 001 |
| 011-impl | outcome-summary — Impl | pending | 011-test |
| 012-test | confidence-legibility — Test | pending | 001 |
| 012-impl | confidence-legibility — Impl | pending | 012-test, 002-impl |

## Key Decisions

- **Harness fixtures live in package-root `backend/tests/conftest.py`** (not `features/conftest.py`) so both `features/` and `unit/` resolve them — `features/conftest.py` is a marker only. Reuse `rest_client`, `mcp_client`, `assert_transport_parity(query, fields)`, `embedding_fault(mode)` and the `_helpers/transports.py` callers (`rest_search`, `mcp_recall`, `best_solution_for`) in all remaining feature tests.
- **Shared read-row builder is `AgentbookService._pick_best_solution` + `_attach_search_provenance`** (Application layer). MCP `recall` returns `service.search_problems(...)` verbatim; REST serializes the same dict. Tasks 010 and 012 EXTEND this same builder — do not fork a second serializer.
- **`confidence_inputs` provenance comes from `_provenance_from_outcomes`** (`service.py:176-185`) — surfaces frozen-math values only. 012-impl (confidence-legibility) builds on this.
- Frozen confidence policy v6 untouched; `scripts/check_frozen_policy.sh` is the authoritative gate. No remaining task may bump `__frozen_policy_version__`.

## File Ownership

| File Path | Last Modified By Task |
|-----------|-----------------------|
| backend/tests/conftest.py | 001 |
| backend/tests/features/conftest.py | 001 |
| backend/tests/features/test_harness_smoke.py | 001 |
| backend/tests/unit/_helpers/__init__.py | 001 |
| backend/tests/unit/_helpers/transports.py | 001 |
| backend/tests/features/transport-read-parity.feature | 002-test |
| backend/tests/unit/test_transport_read_parity.py | 002-test |
| backend/application/service.py | 002-impl |
| backend/presentation/api/schemas.py | 002-impl |
| backend/presentation/api/routes/search.py | 002-impl |

## Blockers

None.

Repo-debt note (pre-existing, not from this plan): `ruff check backend/` flags F401 in `backend/infrastructure/search_stack.py:31` and `backend/tests/eval/test_lift_eligibility.py:10`. Coordinators should scope ruff to their own touched files (per CODE-LINT-01) and not be blocked by these.
