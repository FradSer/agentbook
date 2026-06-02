# Handoff Summary — Batch 2

## Completed Tasks

| ID | Subject | Checklist Result | Batch |
|----|---------|------------------|-------|
| 001 | Shared cross-transport contract test harness | PASS (all items) | 1 |
| 002-test | transport-read-parity — Test (Red) | PASS (all items) | 1 |
| 002-impl | transport-read-parity — Impl (Green) | PASS (all items) | 1 |
| 003-test | contribute-no-silent-failure — Test (Red) | PASS (all items) | 2 |
| 003-impl | contribute-no-silent-failure — Impl (Green) | PASS (all items) | 2 |
| 004-test | write-dedup — Test (Red) | PASS (all items) | 2 |
| 004-impl | write-dedup — Impl (Green) | PASS (all items) | 2 |

## Remaining Tasks

| ID | Subject | Status | Dependencies |
|----|---------|--------|--------------|
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

- **`existing_problems` is now `list[dict]`** (`{problem_id, match_quality, similarity_score, description_preview}`), NOT `list[str]`. Any task reading it uses dict access. Task 005 (honest-match-labeling) touches `match_quality` semantics — reconcile with this shape.
- **Dedup advisory lives in `AgentbookService._dedup_advisory`** (`service.py:1636`), embedding-independent: `find_by_error_signature` leg + keyword leg + optional semantic leg.
- **`ProblemCreateResponse` gained** `solution_id`, `solution_count`, `next_step`, `existing_problems`. **`ProblemCreateRequest` has `extra="forbid"` + a `model_validator`** emitting a guided naming-422 — any NEW request field must be declared on the model or it 422s.
- PR-18 length floor: gate message is `"Solution content must be at least 10 characters"` (`gate.py:73`).
- Shared read-row builder (`_pick_best_solution` + `_attach_search_provenance`) from Batch 1 still backs both transports; tasks 010 + 012 extend it.

## File Ownership

| File Path | Last Modified By Task |
|-----------|-----------------------|
| backend/tests/conftest.py | 001 |
| backend/tests/features/conftest.py | 001 |
| backend/tests/features/test_harness_smoke.py | 001 |
| backend/tests/unit/_helpers/transports.py | 001 |
| backend/tests/features/transport-read-parity.feature | 002-test |
| backend/tests/unit/test_transport_read_parity.py | 002-test |
| backend/application/service.py | 004-impl |
| backend/presentation/api/schemas.py | 004-impl |
| backend/presentation/api/routes/search.py | 002-impl |
| backend/presentation/api/routes/problems.py | 003-impl |
| backend/application/gate.py | 003-impl |
| backend/presentation/mcp/tools.py | 004-impl |
| backend/tests/unit/test_gate.py | 003-impl (invalidated-peer fix) |
| backend/tests/features/contribute-no-silent-failure.feature | 003-test |
| backend/tests/unit/test_contribute_no_silent_failure.py | 003-test |
| backend/tests/features/write-dedup.feature | 004-test |
| backend/tests/unit/test_write_dedup.py | 004-test |

## Blockers

None.

Repo-debt note (pre-existing, not from this plan): `ruff check backend/` flags F401 in `backend/infrastructure/search_stack.py:31` and `backend/tests/eval/test_lift_eligibility.py:10`. Scope ruff to touched files.
