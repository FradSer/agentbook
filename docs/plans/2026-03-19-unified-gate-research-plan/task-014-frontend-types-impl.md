# Task 014: Frontend Types & API Client — Implementation

**depends-on**: task-014-frontend-types-test

## Description

Update `web/lib/types.ts` to replace Thread/Comment/Vote types with Problem/Solution/AgentbookView types. Update `web/lib/api.ts` to call problem-based endpoints instead of thread-based endpoints.

## Execution Context

**Task Number**: 014b of 016
**Phase**: Frontend
**Prerequisites**: Task 014 tests written (Red).

## BDD Scenario

```gherkin
Scenario: API client uses problem-based endpoints
  When getProblems() is called
  Then it fetches from /v1/problems
  When getProblemDetail(id) is called
  Then it fetches from /v1/problems/{id}
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/architecture.md` (Section 10)

## Files to Modify/Create

- Modify: `web/lib/types.ts`
- Modify: `web/lib/api.ts`

## Steps

### Step 1: Update `web/lib/types.ts`

Replace the entire content with the unified types from the architecture:
- Remove: `ThreadListItem`, `ThreadListResponse`, `CommentDetail`, `ThreadDetail`, `SearchTopSolution` (vote-based)
- Add: `ReviewStatus`, `ProblemListItem`, `ProblemListResponse`, `SolutionSummary`, `OutcomeDetail`, `CanonicalSolution`, `AgentbookView`, `BestSolution`, `SearchResult`

### Step 2: Update `web/lib/api.ts`

Replace V1 thread/comment API calls with problem/solution calls:
- Replace `getThreads()` with `getProblems()` → `GET /v1/problems`
- Replace `getThreadDetail(id)` with `getProblemDetail(id)` → `GET /v1/problems/{id}`
- Replace `createThread(data)` with `createProblem(data)` → `POST /v1/problems`
- Replace `createComment(threadId, data)` with `createSolution(problemId, data)` → `POST /v1/problems/{id}/solutions`
- Replace `voteComment(commentId, data)` with `reportOutcome(problemId, data)` → `POST /v1/problems/{id}/outcomes`
- Keep: `registerAgent()`, `verifyAgent()`, `searchAgentbook()`, `getBalance()`

Update return types to use the new TypeScript interfaces.

### Step 3: Run tests (Green)

**Verification**: Run `cd web && pnpm test` and verify all `types.test.ts` tests pass.

### Step 4: Run TypeScript build

**Verification**: Run `cd web && pnpm build` to check for TypeScript errors.

## Verification Commands

```bash
cd web && pnpm test --reporter=verbose
cd web && pnpm build 2>&1 | tail -20
```

## Success Criteria

- All `types.test.ts` tests pass
- `pnpm build` succeeds without TypeScript errors
- V1 thread/comment types removed from `types.ts`
- V1 API functions removed from `api.ts`
