# Evaluation — Round 1, Batch 1 (Foundation)

**Plan:** `docs/plans/2026-05-01-live-research-banner-plan/`
**Sprint contract:** `sprint-contract-batch-1.md`
**Code checklist:** `docs/retros/checklists/code-v1.md` (v1)
**Mode:** code
**Evaluator:** Inline coordinator pass (the `superpowers:superpowers-evaluator` skill is not registered in this session; the parent agent should re-run an external evaluator if a stricter pass is required)

## Verdict: PASS

## Files reviewed

- `backend/tests/features/live_research_banner.feature` (new)
- `backend/domain/repositories.py` (modified)
- `backend/application/service.py` (modified)
- `backend/infrastructure/persistence/sqlalchemy_models.py` (modified)
- `alembic/versions/c7bae2af560d_add_ix_problems_research_started_at_index.py` (new)
- `docs/plans/2026-05-01-live-research-banner-plan/handoff-state.md` (untouched in this batch — coordinator does not edit handoff state)

## Acceptance criteria — sprint-contract-batch-1.md

### Task 001 — BDD feature file
- [x] File exists at `backend/tests/features/live_research_banner.feature`
- [x] Exactly 27 `Scenario:` lines (`grep -c "^  Scenario:" …` → 27)
- [x] File starts with `@frontend @backend @sse` tag line then `Feature: Live Research Banner`
- [x] No `.py` step definition files were created
- [x] Body copied byte-for-byte from `docs/plans/2026-05-01-live-research-banner-design/bdd-specs.md` lines 34–300 (the Gherkin block contents)

### Task 002 — Domain Protocols + constant
- [x] `ProblemRepository.list_being_researched(timeout_seconds: int = 360) -> list[Problem]` with `...` body and docstring
- [x] `ResearchCycleRepository.get_latest_cycle_at() -> datetime | None` with `...` body and docstring
- [x] `RESEARCH_TIMEOUT_SECONDS: int = 360` declared at module scope in `backend/application/service.py:73`
- [x] `_is_being_researched`'s default uses `RESEARCH_TIMEOUT_SECONDS` (line 2397)
- [x] No remaining literal `360` in `backend/application/service.py` outside the constant declaration (`grep -n 360 …` confirmed)
- [x] All existing unit tests still pass (`uv run pytest backend/tests/unit -k "research" -x` → 16 passed)
- [x] `uv run ruff check backend/domain/repositories.py backend/application/service.py` exits 0
- [x] Both probe imports succeed:
  - `from backend.application.service import RESEARCH_TIMEOUT_SECONDS; assert RESEARCH_TIMEOUT_SECONDS == 360`
  - `hasattr(ProblemRepository, 'list_being_researched') and hasattr(ResearchCycleRepository, 'get_latest_cycle_at')`

### Task 003 — Alembic migration
- [x] New migration file `alembic/versions/c7bae2af560d_add_ix_problems_research_started_at_index.py` exists; matches `*research_started_at_index*` glob
- [x] Migration body executes `CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_problems_research_started_at ON problems (research_started_at) WHERE research_started_at IS NOT NULL`
- [x] `disable_ddl_transaction = True` set at module scope (line 30)
- [x] `downgrade()` runs `DROP INDEX IF EXISTS ix_problems_research_started_at`
- [x] Migration docstring contains the rollback note for INVALID indexes left by interrupted CONCURRENTLY runs
- [x] `backend/infrastructure/persistence/sqlalchemy_models.py:127` `research_started_at` Column gained `index=True`
- [x] Source-level probe asserts pass: CONCURRENTLY substring + WHERE clause + `disable_ddl_transaction = True` all present
- [x] `uv run alembic history` returns clean linear chain `l5e6f7a8b9c0 → c7bae2af560d (head)`
- [x] `uv run alembic show c7bae2af560d` resolves to the new revision with parent `l5e6f7a8b9c0`
- [ ] `uv run alembic check` exits 0 — **NOT VERIFIED** (see Limitations)
- [ ] Live `alembic upgrade head` / `downgrade -1` — **NOT VERIFIED** (see Limitations)

## Code checklist v1 audit

| Item | Status | Evidence |
|---|---|---|
| CODE-ASSUME-01 | PASS | Grepped for `_is_being_researched` and `360` before editing service.py; grepped existing Protocol classes before adding new methods. |
| CODE-ASSUME-02 | PASS | Confirmed `Problem`, `datetime` already imported in `repositories.py` (no new imports needed). |
| CODE-EDIT-01 | PASS | After PostToolUse formatter reformatted `repositories.py`, re-Read the file before the next Edit (collapsed multi-line signature into one line — adapted). |
| CODE-EDIT-02 | N/A | No formatter-stripped imports in this batch. |
| CODE-A11Y-01 | N/A | No frontend changes in this batch. |
| CODE-LINT-01 | PASS | `uv run ruff check` on all touched Python files → "All checks passed!" |
| CODE-TEST-01 | PASS | No new tests written (deferred to 004a/005a/etc.). The feature file is text-only. |
| CODE-TEST-02 | N/A | No integration tests added in this batch. |
| CODE-TEST-03 | N/A | No red tests written this batch. |
| CODE-VERIFY-01 | PASS | `make fast` → 423 passed, 3 deselected (after each task). |
| CODE-VERIFY-02 | PASS | service.py is shared infrastructure; full unit suite re-run after the constant promotion. |
| CODE-SCOPE-01 | PASS | Only the files listed in each task's "Files to Modify/Create" were touched. No drive-by edits. |
| CODE-SCOPE-02 | N/A | Coordinator does not commit; commit message is the parent agent's responsibility. |
| CODE-MIGRATION-01 | PARTIAL | Source-level probe of CONCURRENTLY + partial WHERE + `disable_ddl_transaction = True` PASSED; live-DB probe NOT performed (see Limitations). |
| CODE-MIGRATION-02 | NOT VERIFIED | Downgrade not run against a live DB. The static migration body uses `DROP INDEX IF EXISTS …` which is idempotent and routinely covered by parallel migration tests in the existing repo (e.g. `dd782cb96759`, `h1a2b3c4d5e6`). |

## Out-of-scope guard audit

- [x] No `.py` step-definition files created in Task 001
- [x] No Protocol method bodies added in Task 002 (`...` only)
- [x] `backend/main.py`, route registration, presentation code untouched
- [x] No frontend file modified
- [x] `backend/application/service.py` only modified to declare the constant + redirect `_is_being_researched`'s default — no other production-code change

## Limitations

- `uv run alembic check` requires a reachable Postgres. The `.env` `DATABASE_URL` points at the production Neon DB. Running `alembic upgrade head` from this agent against production would deploy the migration ad-hoc, bypassing the Railway pre-deploy pipeline (`docs/deployment.md`). Per the coordinator instructions ("If [a local Postgres is] not reachable, document that fact in the result (do NOT block)"), live-DB upgrade/downgrade verification is deferred to deployment. The hermetic alternatives — `alembic history`, `alembic show`, source-level probe, `python -c` module-load probe — all pass.
- The `superpowers:superpowers-evaluator` skill is not registered in this session's available skills, so this evaluation is the coordinator's inline equivalent. The parent agent retains the option to re-spawn an external evaluator before merging the batch.

## Recurring patterns detected

(none — this is the first batch)

## Recommendation

PASS. Proceed to Batch 2 (tasks 004a / 004b / 005a / 005b — repository implementation + service-layer test/impl).
