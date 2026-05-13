# Task 013: Wire <LiveResearchBanner/> into frontend/app/page.tsx + smoke verify

**depends-on**: 012b, 009b

## Description

Insert `<LiveResearchBanner/>` into the homepage between the hero subtitle block and the `<Tabs>` block. Verify the per-card `Researching` badge still renders for visible cards (the banner is additive). Run the full smoke pipeline. This is the final visible-to-user task.

## Execution Context

**Task Number**: 013 of 20 (final)
**Phase**: Frontend — Wire-in + Smoke
**Prerequisites**: Task 012b (banner component), Task 009b (SSE backend live).

## BDD Scenario

```gherkin
Scenario: Banner mounts between hero subtitle and Tabs in document order
  Given the homepage is mounted
  When the document is queried for landmark order
  Then the banner element appears after the hero subtitle paragraph
  And the banner element appears before the Tabs region with role "tablist"
  And the banner is part of normal document flow (not position: fixed or sticky)

Scenario: Per-card Researching badge continues to render alongside the banner
  Given problem "P-1" has fresh research_started_at
  And "P-1" is visible on the Memories tab
  When the homepage renders the banner showing "P-1"
  Then the ProblemCard for "P-1" still renders the "Researching" badge
  And the ProblemCard for "P-1" still applies the ".research-active" class
  And the banner and the per-card badge stay in sync on the next state change
```

**Spec Source**: `../2026-05-01-live-research-banner-design/bdd-specs.md`

## Files to Modify/Create

- Modify: `frontend/app/page.tsx`
- Modify: `frontend/tests/pages.test.tsx` or `frontend/tests/human-page.test.tsx` (whichever currently covers the homepage layout — verify via `grep -l "HomePage\|page.tsx" frontend/tests/`)

## Steps

### Step 1: Insert the banner

In `frontend/app/page.tsx`, locate the hero block at lines 540-556 (ending with the `<p className="max-w-2xl …">` paragraph) and the `<Tabs>` block starting at line 563. Insert the banner between them:

```tsx
import { LiveResearchBanner } from "@/components/app/live-research-banner";

// ... existing component body ...

return (
  <div>
    {/* Header */}
    <div className="mb-6 pt-4 sm:mb-8 sm:pt-6 pl-5 space-y-3">
      {/* ... existing hero content unchanged ... */}
    </div>

    {/* Live research banner */}
    <div className="mb-6 px-3 sm:mb-8">
      <LiveResearchBanner />
    </div>

    {/* Tab bar */}
    {/* ... existing <Tabs> block unchanged ... */}
  </div>
);
```

The wrapper `<div>` carries the same horizontal padding as the rest of the page so the banner aligns with the Tabs and the problem grid.

### Step 2: Add the placement BDD scenarios as test cases

Add two test cases to the existing homepage test file (or `pages.test.tsx`):

```typescript
test("banner mounts after hero subtitle and before Tabs region", () => {
  /** Render <HomePage/>, query banner element by role='status' or test-id,
   *  query Tabs by role='tablist'. Assert document.body order via
   *  compareDocumentPosition. */
  ...
});

test("ProblemCard Researching badge still renders when banner is mounted", () => {
  /** Mock api with one fresh problem; render <HomePage/>; assert the
   *  page contains BOTH the banner badge AND the per-card badge. */
  ...
});
```

### Step 3: Run the full frontend pipeline
```bash
cd frontend && pnpm test
cd frontend && pnpm lint
cd frontend && pnpm build
```

All must succeed with zero errors.

### Step 4: Run the full backend pipeline
```bash
make fast
```

The 27 BDD scenarios should be exercised by the tests landed in earlier tasks.

### Step 5: End-to-end smoke (manual)

```bash
# Terminal 1: backend
DEMO_MODE=1 uv run uvicorn backend.main:app --reload

# Terminal 2: frontend
cd frontend && pnpm dev

# Browser: http://localhost:3000
```

Visual checklist:

- Banner is visible between the hero text and the Tabs.
- In `DEMO_MODE`, no problem is being researched → banner shows `"Idle · last cycle Xm ago"` or `"Idle · awaiting first cycle"`.
- Manually toggle a research_started_at via the SQL console (or temporarily seed a fresh row in `backend/demo.py`) and observe the banner switch to active state within ~2 s.
- Disable network in DevTools for 30 s, watch the `(reconnecting)` hint appear; restore network and watch it return to live.
- Toggle `prefers-reduced-motion: reduce` in DevTools rendering panel and confirm the pulse stops.

### Step 6: Format and lint
```bash
uv run ruff check .
cd frontend && pnpm lint
```

## Verification Commands

```bash
cd frontend && pnpm test
cd frontend && pnpm lint
cd frontend && pnpm build
make fast
```

## Success Criteria

- `<LiveResearchBanner/>` rendered in `frontend/app/page.tsx` between hero and Tabs.
- Two new homepage placement tests pass.
- All 18 banner-component tests still pass after the wire-in.
- All 14 hook tests still pass.
- Existing per-card `Researching` badge rendering still works on the Memories tab.
- `pnpm build` succeeds with zero errors.
- `make fast` passes.
- `cd frontend && pnpm lint && pnpm build` passes.
- Manual smoke checklist passes against `DEMO_MODE=1` backend + dev frontend.
