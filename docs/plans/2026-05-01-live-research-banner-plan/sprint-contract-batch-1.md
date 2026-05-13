# Sprint Contract — Batch 1 (Foundation)

**Plan:** `docs/plans/2026-05-01-live-research-banner-plan/`
**Batch:** 1 of 7
**Mode:** Linear (sequential dependency chain 001 → 002 → 003)
**Code checklist:** `docs/retros/checklists/code-v1.md` (v1)

## Tasks in this batch

| Plan ID | TaskList ID | Subject | Depends-on |
|---|---|---|---|
| 001 | 1 | Land BDD feature file with all 27 scenarios | (none) |
| 002 | 2 | Domain Protocol additions and RESEARCH_TIMEOUT_SECONDS constant | 001 |
| 003 | 3 | Alembic migration for ix_problems_research_started_at partial index | 002 |

## Acceptance Criteria (auto-derived from task files' Success Criteria + BDD Then-clauses)

### Task 001 — BDD feature file
- File `backend/tests/features/live_research_banner.feature` exists.
- Exactly 27 `Scenario:` lines (`grep -c "^  Scenario:" …` → 27).
- File starts with `Feature: Live Research Banner` header (preceded by `@frontend @backend @sse` tags).
- No `.py` step definition files created in this task.
- Body copied byte-for-byte from `docs/plans/2026-05-01-live-research-banner-design/bdd-specs.md` Gherkin block.

### Task 002 — Domain Protocols + constant
- `ProblemRepository.list_being_researched(timeout_seconds: int = 360) -> list[Problem]` Protocol method present (signature only, body is `...`).
- `ResearchCycleRepository.get_latest_cycle_at() -> datetime | None` Protocol method present (signature only).
- `RESEARCH_TIMEOUT_SECONDS: int = 360` declared at module scope in `backend/application/service.py`.
- `_is_being_researched(problem, timeout_seconds=RESEARCH_TIMEOUT_SECONDS)` default uses the constant.
- No remaining literal `360` in `backend/application/service.py` related to research timeout.
- All existing unit tests (`uv run pytest backend/tests/unit -k "research" -x`) still pass.
- `uv run ruff check backend/domain/repositories.py backend/application/service.py` exits 0.
- Verification probes pass:
  - `from backend.application.service import RESEARCH_TIMEOUT_SECONDS; assert RESEARCH_TIMEOUT_SECONDS == 360`
  - `hasattr(ProblemRepository, 'list_being_researched')` and `hasattr(ResearchCycleRepository, 'get_latest_cycle_at')`

### Task 003 — Alembic migration
- New migration file in `alembic/versions/` matching `*research_started_at_index*.py`.
- Migration uses `CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_problems_research_started_at ON problems (research_started_at) WHERE research_started_at IS NOT NULL`.
- `disable_ddl_transaction = True` set.
- `downgrade()` runs `DROP INDEX IF EXISTS ix_problems_research_started_at`.
- Migration docstring includes the rollback note for INVALID indexes left by interrupted CONCURRENTLY runs.
- `backend/infrastructure/persistence/sqlalchemy_models.py:~126` `research_started_at` Column gains `index=True` for ORM/dev parity.
- `uv run alembic check` exits 0.
- Migration verification probe passes (CONCURRENTLY substring + WHERE clause + disable_ddl_transaction in source).
- If a local Postgres is available: `alembic upgrade head` and `alembic downgrade -1` both succeed; if not, document the limitation in the batch result.

## Code checklist v1 — items most relevant this batch

- **CODE-ASSUME-01 / CODE-ASSUME-02**: grep for existing names before writing tests / imports (Tasks 002, 003).
- **CODE-EDIT-01 / CODE-EDIT-02**: re-Read after formatter ran (`ruff` may rewrite imports in `service.py` after Step 2).
- **CODE-LINT-01**: every task concludes with `uv run ruff check …` on touched files.
- **CODE-VERIFY-01**: full unit-suite regression must pass before marking each task complete (`make fast` or `uv run pytest backend/tests/unit -x`).
- **CODE-SCOPE-01**: only files listed in each task's "Files to Modify/Create" change.
- **CODE-MIGRATION-01**: schema probe required for Task 003 — confirm migration source contains CONCURRENTLY + the partial WHERE clause; if Postgres available, run upgrade/downgrade and verify the index.

## Out-of-scope guards

- Do NOT create step definition `.py` files for the feature scenarios in Task 001 — those land in later test tasks (004a–012a).
- Do NOT add Protocol method bodies in Task 002 — only signatures with `...`.
- Do NOT touch `backend/main.py`, route registration, or any presentation code in this batch.
- Do NOT modify any frontend file in this batch.
- Do NOT write production code in `backend/application/service.py` beyond promoting the literal `360` to a constant and updating `_is_being_researched`'s default.

## Verification commands (per task)

### Task 001
```bash
test -f backend/tests/features/live_research_banner.feature
grep -c "^  Scenario:" backend/tests/features/live_research_banner.feature   # → 27
grep -c "^@" backend/tests/features/live_research_banner.feature              # → ≥ 1
```

### Task 002
```bash
uv run ruff check backend/domain/repositories.py backend/application/service.py
uv run python -c "from backend.application.service import RESEARCH_TIMEOUT_SECONDS; assert RESEARCH_TIMEOUT_SECONDS == 360"
uv run python -c "from backend.domain.repositories import ProblemRepository, ResearchCycleRepository; assert hasattr(ProblemRepository, 'list_being_researched'); assert hasattr(ResearchCycleRepository, 'get_latest_cycle_at')"
uv run pytest backend/tests/unit -k "research" -x
```

### Task 003
```bash
ls alembic/versions/ | grep "research_started_at_index"
uv run alembic check
uv run python -c "import pathlib, re; src = open([p for p in pathlib.Path('alembic/versions').glob('*research_started_at_index*')][0]).read(); assert 'CONCURRENTLY' in src; assert 'WHERE research_started_at IS NOT NULL' in src; assert 'disable_ddl_transaction = True' in src"
```

### Full-batch regression (CODE-VERIFY-01)
```bash
make fast
```
