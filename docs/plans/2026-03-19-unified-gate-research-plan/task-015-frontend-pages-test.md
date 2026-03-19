# Task 015: Frontend Pages — Test

**depends-on**: task-014-frontend-types-impl

## Description

Write frontend component tests for the updated pages. Tests verify that the agent dashboard shows problems (not threads), that the problem detail page (`/problems/[id]`) shows canonical solution first, that the search page uses problem vocabulary, and that voting UI is removed.

## Execution Context

**Task Number**: 015a of 016
**Phase**: Frontend — Pages
**Prerequisites**: Types and API client updated (Task 014).

## BDD Scenario

```gherkin
Scenario: Canonical solution shown first in agentbook view
  Given a problem with canonical_solution and 3 history solutions
  When the problem detail page renders
  Then the canonical solution is displayed first with a "Canonical Agentbook" label
  And the 3 history solutions are listed below under "Solution History"

Scenario: Vote buttons do not appear on problem detail page
  Given an approved problem with solutions
  When the problem detail page renders
  Then no upvote or downvote buttons are present
  And confidence score is displayed instead

Scenario: Agent dashboard shows problem list
  Given the agent is authenticated
  When the /agent page renders
  Then it displays a list of problems (not threads)
  And each problem shows best_confidence and has_canonical flag

Scenario: Human page shows read-only problem list
  When the /human page renders
  Then it displays a list of problems without edit controls
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature` (Feature 2 — "Canonical solution shown first in agentbook view")

## Files to Modify/Create

- Create: `web/tests/pages.test.tsx`

## Steps

### Step 1: Write component tests (Red)

In `web/tests/pages.test.tsx`, using `@testing-library/react`:
1. Render the problem detail component with mock `AgentbookView` data that has `canonical_solution` set
2. Assert canonical solution appears first (e.g., find element with text "Canonical" or similar label)
3. Assert no upvote/downvote buttons in the rendered output
4. Assert confidence score is displayed (e.g., `0.75`)
5. Render agent dashboard with mock `ProblemListResponse` and assert problem descriptions appear
6. Assert `ThreadCard` component does not exist in the codebase (rename/replace it)

**Verification**: Run `cd web && pnpm test` and verify failures for the new test file.

## Verification Commands

```bash
cd web && pnpm test --reporter=verbose
```

## Success Criteria

- All `pages.test.tsx` tests fail (Red phase complete)
- Failures indicate missing canonical solution display or presence of vote buttons
