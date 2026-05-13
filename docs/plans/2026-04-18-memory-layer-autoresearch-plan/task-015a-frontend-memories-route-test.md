# Task 015a: Frontend /memories route plus 308 redirects — Red

**depends-on**: (none)

## Description

Red tests for the Next.js route reorg. `/memories` is the new primary listing. `/problems` and `/problems/[id]` 308-redirect to their `/memories` counterparts. Both redirects preserve method and body (308 semantics).

## Execution Context

**Task Number**: 015a of 41
**Phase**: Frontend reorg
**Prerequisites**: none (pure frontend).

## BDD Scenario

```gherkin
Scenario: /problems redirects to /memories (308)
  When a browser requests GET /problems
  Then the server returns HTTP 308 to /memories
  And the browser caches the redirect across sessions

Scenario: /problems/[id] redirects to /memories/[id] (308)
  When a browser requests GET /problems/abc-123
  Then the server returns HTTP 308 to /memories/abc-123
```

**Spec Source**: `../2026-04-18-memory-layer-autoresearch-design/bdd-specs.md`

## Files to Modify/Create

- Create: `frontend/tests/routes-redirect.test.ts` — vitest + Next.js test runner. Or `frontend/tests/e2e/memories-route.spec.ts` if Playwright is used (check `frontend/package.json` for the configured runner).

## Steps

### Step 1: Tests
- `test_problems_list_redirects_308_to_memories` — fetch `/problems` from the Next dev server; assert status 308 and `Location: /memories`.
- `test_problems_detail_redirects_308_to_memories_detail` — fetch `/problems/abc-123`; assert status 308 and `Location: /memories/abc-123`.
- `test_memories_list_page_renders` — request `/memories`; assert status 200 and page contains the "Memories" heading.
- `test_memories_detail_page_renders` — seed an API fixture; request `/memories/<id>`; assert page renders the memory heading.

### Step 2: Confirm Red
- All four tests fail because `/memories` does not yet exist and `next.config.mjs` has no redirect rule.

## Verification Commands

```bash
cd frontend && pnpm test tests/routes-redirect.test.ts
```

## Success Criteria

- Four failing tests.
- Follow the test style already used in `frontend/tests/` (vitest + jsdom or Playwright — match the repo).
