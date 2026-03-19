# Task 014: Frontend Types & API Client — Test

**depends-on**: task-011-api-routes-impl

## Description

Write frontend unit tests verifying that the TypeScript type definitions match the backend API schemas, that the API client functions call the correct problem-based endpoints, and that all V1 thread/comment types are removed.

## Execution Context

**Task Number**: 014a of 016
**Phase**: Frontend
**Prerequisites**: API routes and schemas implemented (Task 011).

## BDD Scenario

```gherkin
Scenario: API client calls /v1/problems endpoint
  Given the API client is initialized with a base URL
  When getProblems() is called
  Then a GET request is made to /v1/problems

Scenario: AgentbookView type has canonical_solution field
  Given TypeScript types are imported
  Then AgentbookView.canonical_solution is typed as CanonicalSolution | null
  And AgentbookView.solution_history is typed as SolutionSummary[]

Scenario: Thread and Comment types no longer exist
  Given the types module is imported
  Then ThreadListItem cannot be imported
  And CommentDetail cannot be imported
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/architecture.md` (Section 10)

## Files to Modify/Create

- Create: `web/tests/types.test.ts`

## Steps

### Step 1: Write TypeScript type tests (Red)

In `web/tests/types.test.ts`:
1. Import types from `@/lib/types` and verify `AgentbookView` has `canonical_solution`, `solution_history`, `best_confidence`, `has_canonical` fields
2. Verify `ProblemListItem` has `problem_id`, `description`, `best_confidence`, `has_canonical` fields
3. Verify `SolutionSummary` has `confidence`, `outcome_count`, `success_count` fields (not `upvotes`, `downvotes`, `wilson_score`)
4. Verify `ThreadListItem` and `CommentDetail` are NOT exported from `@/lib/types`

For the API client tests:
1. Mock `fetch` and verify `getProblems()` calls `GET /v1/problems`
2. Verify `getProblemDetail(id)` calls `GET /v1/problems/{id}`
3. Verify `createProblem(data)` calls `POST /v1/problems`
4. Verify `createSolution(problemId, data)` calls `POST /v1/problems/{id}/solutions`
5. Verify `reportOutcome(problemId, data)` calls `POST /v1/problems/{id}/outcomes`
6. Verify `getThreads`, `createThread`, `createComment`, `voteComment` are NOT exported from `@/lib/api`

**Verification**: Run `cd web && pnpm test` and verify failures.

## Verification Commands

```bash
cd web && pnpm test --reporter=verbose
```

## Success Criteria

- All `types.test.ts` tests fail (Red phase complete)
- Failures confirm V1 types still exist and V2 types are missing
