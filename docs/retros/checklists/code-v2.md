# Code Mode Checklist — v2

Evolved from `code-v1.md` by `retro-2026-06-02-banner-outcome-loop`. Single change vs v1: **CODE-SCOPE-02 removed** — it was N/A in all 10 per-batch code reports because per-batch coordinators never commit (commit is the parent agent's job). The commit-message-scope concern is a commit-time check (handled by the `git:commit` skill), not a per-task code-batch gate. No signal lost; checklist load reduced. All other items unchanged.

Items apply per-task during executing-plans batch verification.

## No-assumption rule

- **CODE-ASSUME-01**: Before writing a test that references a fixture, helper, repository method, or attribute by name, grep for its existence in the target module or conftest. Do not invent names.
- **CODE-ASSUME-02**: Before importing a type from a shared module (`@/lib/types`, `backend/domain/models`, etc.), confirm the exact exported name. Renamed types (`Problem` → `ProblemListItem`) must be checked, not guessed.

## Edit-after-formatter hygiene

- **CODE-EDIT-01**: If a PostToolUse hook reformats a file after a Write, Read the file before the next Edit targeting that file. `old_string` anchored to pre-reformatter content will fail.
- **CODE-EDIT-02**: When a formatter auto-removes an import (e.g. Biome removing "unused" router imports), re-add it adjacent to other imports in the same module rather than inserting at the top of the file alone — the reformatter will strip it again.

## a11y and linting

- **CODE-A11Y-01**: `aria-label` on a plain `<span>` or `<div>` requires an accompanying `role="img"` (or equivalent) to satisfy Biome's `useAriaPropsSupportedByRole`.
- **CODE-LINT-01**: Every task concludes with a lint run (`pnpm lint` / `uv run ruff check`) before marking completed. Lint failures unblocked by the task block completion.

## Test double isolation at boundaries

- **CODE-TEST-01**: Unit tests must not hit a real database, network, or third-party API. Use in-memory repos, fake providers, or clock fixtures.
- **CODE-TEST-02**: Integration tests that require Docker/Postgres are gated behind `RUN_DOCKER_TESTS=1` or equivalent env check so CI default runs stay hermetic.
- **CODE-TEST-03**: Red tests assert the failure mode is the one the feature would produce, not an incidental collection error (missing fixture, import error) — re-run and confirm the assertion fires on the expected line.

## Verification gate

- **CODE-VERIFY-01**: Before marking a task completed, the test command from the task file exits 0 AND the full-suite regression command also exits 0. Isolated green tests with broken peers do not count.
- **CODE-VERIFY-02**: Intermediate refactors that touch shared infrastructure (`confidence.py`, `service.py`, router registration) re-run the entire unit suite, not just the feature's tests.

## Scope discipline

- **CODE-SCOPE-01**: A task changes only the files listed in its "Files to Modify/Create" section, with the exceptions: (a) adding a missing import into its natural group, (b) correcting a broken pre-existing test whose assertion the task's own implementation invalidated. Out-of-scope changes need a follow-up task, not silent inclusion.

## Migration hygiene

- **CODE-MIGRATION-01**: Alembic migrations are applied against a live database and a schema probe confirms the expected change (column exists, NOT NULL, CHECK constraint active) before the task is marked complete.
- **CODE-MIGRATION-02**: Downgrade paths run cleanly against the upgraded schema when practical.
