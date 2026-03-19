# Task 016: Cleanup & Service Construction

**depends-on**: task-011-api-routes-impl, task-012-mcp-tools-impl, task-013-reviewer-agent-impl, task-015-frontend-pages-impl

## Description

Final cleanup: update `app/main.py` and `agent/src/main.py` service construction (drop V1 repo references), verify all dead code files are deleted, run the full test suite and build verification, update `scripts/smoke_test.sh` for the new endpoints, and update `CLAUDE.md`.

## Execution Context

**Task Number**: 016 of 016
**Phase**: Integration & Cleanup
**Prerequisites**: All prior implementation tasks complete.

## BDD Scenario

```gherkin
Scenario: Service is constructed without V1 repositories
  Given the app starts with no DATABASE_URL
  When _build_service() is called
  Then AgentbookService is constructed with InMemoryProblemRepository
  And InMemorySolutionRepository, InMemoryOutcomeRepository, etc.
  And no threads, comments, or votes repositories are passed

Scenario: Full test suite passes
  Given all implementation tasks are complete
  When uv run pytest tests/unit/ is run
  Then all unit tests pass with no failures

Scenario: Frontend build succeeds
  When cd web && pnpm build is run
  Then the build completes without errors
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/architecture.md` (Section 9.2 + 9.3)

## Files to Modify/Create

- Modify: `app/main.py`
- Modify: `agent/src/main.py`
- Modify: `scripts/smoke_test.sh`

## Steps

### Step 1: Update `app/main.py` service construction

Update `_build_service()` to:
- Remove `threads`, `comments`, `votes` from both SQLAlchemy and in-memory constructions
- Pass only: `agents`, `problems`, `solutions`, `outcomes`, `transactions`, `research_cycles`
- Verify the FastAPI app lifespan startup logic still works

### Step 2: Update `agent/src/main.py` service construction

Update `create_service(session)` to:
- Remove `threads`, `comments`, `votes` repository instantiation
- Pass only unified repositories to `AgentbookService`
- Verify the polling loop still calls `review_content()` (not `run_cycle()`)

### Step 3: Verify deleted files

Confirm these files have been deleted (from prior tasks):
- `app/domain/scoring.py` (Task 002)
- `app/application/quality_gate.py` (Task 005)
- `agent/src/rules.py` (Task 013)
- `app/presentation/api/routes/threads.py` (Task 011)
- `web/app/threads/[id]/page.tsx` (Task 015)

If any remain, delete them now.

### Step 4: Update `scripts/smoke_test.sh`

Update the smoke test script to use the new endpoints:
- Replace `POST /v1/threads` with `POST /v1/problems`
- Replace `GET /v1/threads` with `GET /v1/problems`
- Replace `GET /v1/threads/{id}` with `GET /v1/problems/{id}`
- Replace `POST /v1/threads/{id}/comments` with `POST /v1/problems/{id}/solutions`
- Remove the vote endpoint test (`POST /v1/threads/comments/{id}/vote`)

### Step 5: Run full unit test suite

**Verification**: Run `uv run pytest tests/unit/ -q` and verify no failures.

### Step 6: Run frontend checks

**Verification**: Run `cd web && pnpm lint && pnpm build`.

### Step 7: Run Python linting

**Verification**: Run `uv run ruff check app/ agent/` (if ruff is configured) to confirm no imports of deleted modules.

## Verification Commands

```bash
# Required (no external dependencies)
uv run pytest tests/unit/ -q --tb=short
uv run pytest agent/tests/ -q --tb=short
cd web && pnpm lint && pnpm build

# Optional — requires ruff to be configured in pyproject.toml
uv run ruff check app/ agent/ 2>/dev/null || echo "ruff not configured, skipping"

# Manual — requires a running API server and jq installed
# ./scripts/smoke_test.sh
```

## Success Criteria

- All unit tests pass
- Frontend build succeeds
- `app/main.py` and `agent/src/main.py` construct service without V1 repos
- `smoke_test.sh` updated for new endpoints
- All dead code files deleted
