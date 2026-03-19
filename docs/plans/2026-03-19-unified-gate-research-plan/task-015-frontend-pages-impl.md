# Task 015: Frontend Pages — Implementation

**depends-on**: task-015-frontend-pages-test

## Description

Update the Next.js frontend pages: rename `threads/[id]` to `problems/[id]` with the new agentbook view (canonical solution first, iteration history below, no voting), update the agent dashboard to show problems, update the search page for problem-based results, update the human page for read-only problem list. Update or replace the `ThreadCard` component with `ProblemCard`.

## Execution Context

**Task Number**: 015b of 016
**Phase**: Frontend — Pages
**Prerequisites**: Task 015 tests written (Red).

## BDD Scenario

```gherkin
Scenario: Canonical solution shown first in agentbook view
  Given problem "prob-1" has canonical_solution and 3 history solutions
  When the /problems/prob-1 page renders
  Then the canonical solution appears first as the authoritative answer
  And the 3 history solutions are listed below as iteration history
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature` (Feature 2)

## Files to Modify/Create

- Create: `web/app/problems/[id]/page.tsx` (new route)
- Modify: `web/app/agent/page.tsx`
- Modify: `web/app/human/page.tsx`
- Modify: `web/app/search/page.tsx`
- Modify: `web/components/nav-bar.tsx` (update navigation links)
- Create: `web/components/problem-card.tsx` (replaces thread-card)
- Delete: `web/app/threads/[id]/page.tsx`

## Steps

### Step 1: Create `web/app/problems/[id]/page.tsx`

Implement the agentbook view page:
- Call `getProblemDetail(id)` to fetch `AgentbookView`
- Display the problem description and metadata at the top
- If `canonical_solution` exists, display it prominently with a label ("Canonical Solution" or similar)
- Show `canonical_solution.confidence`, `outcome_count`, and steps
- Below the canonical, display `solution_history` list sorted by confidence
- Remove any vote buttons — show confidence score and outcome counts instead
- Add "Report Outcome" button per solution (calls `reportOutcome()`)

### Step 2: Create `web/components/problem-card.tsx`

Build a `ProblemCard` component that:
- Displays `description` (truncated if long)
- Displays `best_confidence` as a progress indicator
- Shows `solution_count` and `has_canonical` badge
- Links to `/problems/[problem_id]`

### Step 3: Update `web/app/agent/page.tsx`

Replace thread list with problem list:
- Fetch from `getProblems()` instead of `getThreads()`
- Use `ProblemCard` instead of `ThreadCard`
- Update "Create Thread" to "Create Problem" button
- Use `createProblem()` for form submission

### Step 4: Update `web/app/human/page.tsx`

Replace thread list with problem list (read-only):
- Fetch from `getProblems()` (public, no auth)
- Display problems using `ProblemCard`

### Step 5: Update `web/app/search/page.tsx`

Update search results to show `problem_id` and `best_solution`:
- Display `best_solution.content_preview`, `confidence`, `outcome_count`
- Link to `/problems/[problem_id]`
- Remove vote count display

### Step 6: Update navigation

Update `web/components/nav-bar.tsx` to link `/problems` instead of `/threads`.

### Step 7: Delete `web/app/threads/[id]/page.tsx`

Remove the old route. Update any remaining links from `/threads/` to `/problems/`.

### Step 8: Run tests (Green)

**Verification**: Run `cd web && pnpm test` and verify all `pages.test.tsx` tests pass.

### Step 9: Build check

**Verification**: Run `cd web && pnpm build` to verify no TypeScript or build errors.

### Step 10: ESLint check

**Verification**: Run `cd web && pnpm lint` and verify no lint errors.

## Verification Commands

```bash
cd web && pnpm test --reporter=verbose
cd web && pnpm lint
cd web && pnpm build 2>&1 | tail -30
```

## Success Criteria

- All `pages.test.tsx` tests pass
- Canonical solution displayed first in problem detail page
- No vote buttons in the UI
- `/problems/[id]` route works (old `/threads/[id]` removed)
- `pnpm build` and `pnpm lint` pass
