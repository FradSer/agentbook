# Task 012a: <LiveResearchBanner/> component — Red

**depends-on**: 010

## Description

Add failing vitest + jsdom tests for the `<LiveResearchBanner/>` component. Cover all 11 frontend banner scenarios from the BDD spec: active rendering, multi-problem foregrounding, idle copy variants, transition without flash, initial REST snapshot painting, reduced-motion, click-through link, aria-live debounce, CSS token reuse, line-clamp, and the "(reconnecting)" hint when the hook is in fallback mode. Tests must FAIL until task 012b lands.

## Execution Context

**Task Number**: 012a of 20
**Phase**: Frontend — Component Red
**Prerequisites**: Task 010 (types).

## BDD Scenario

```gherkin
Scenario: Single problem under active research populates the banner
  Then the banner renders the title of "P-1"
  And the banner renders the solution_count of "P-1"
  And the banner renders the best_confidence of "P-1" as a percentage
  And the banner renders an "started Xs ago" sublabel
  And the banner uses the existing ".research-active" container class
  And the banner uses the existing "Researching" badge variant

Scenario: Multiple problems researched concurrently shows count and most-recent
  Then the banner foregrounds the title of "P-3"
  And the banner shows a quiet "+2 more in flight" suffix
  And the click target is "/memories/P-3"

Scenario: Transition from researching to idle without UI flash
  Then the banner renders "Idle - last cycle 3m ago"
  And the indicator dot stops animating
  And no skeleton or shimmer appears between the two states

Scenario: Cold start with no completed cycles ever
  Then the banner renders "Idle - awaiting first cycle"

Scenario: Initial paint uses REST snapshot to avoid an idle->active flash
  Then the banner renders "P-1" before the SSE stream's first frame arrives
  And no idle-state copy is ever rendered for the duration of the page load

Scenario: Reduced-motion users see a static glow
  Then the ".research-active::before" pseudo-element does not animate
  And its opacity is fixed at 0.5

Scenario: Banner is a link to the active problem's agentbook page
  Then the browser navigates to "/memories/P-1"
  And the link uses the shared "focusRing" utility for keyboard focus

Scenario: A11y - aria-live announces transitions politely
  Then the banner has role "status"
  And the banner has aria-live "polite"
  And announcements are debounced so two transitions within 1 second yield one announce

Scenario: Banner reuses existing CSS tokens with no new ones introduced
  Then the rendered DOM uses class "research-active"
  And the rendered DOM uses class "researching-dot"
  And the rendered DOM uses the "Researching" badge variant
  And no new CSS custom properties are defined for this feature

Scenario: Long problem descriptions are truncated client-side
  Then the visible text uses Tailwind class "line-clamp-1"
  And the underlying anchor's accessible name is the full description
```

**Spec Source**: `../2026-05-01-live-research-banner-design/bdd-specs.md`

## Files to Modify/Create

- Create: `frontend/tests/live-research-banner.test.tsx`

## Steps

### Step 1: Write failing tests (Red)

Required test contracts:

```typescript
test("renders active problem title, solution count, and confidence percent", () => { ... });

test("active link points at /memories/{problem_id}", () => { ... });

test("renders 'started Xs ago' sublabel using getRelativeTime", () => { ... });

test("multi-problem state foregrounds the most-recent and shows '+N more in flight'", () => { ... });

test("idle state with last_cycle_at renders 'Idle - last cycle Xm ago'", () => { ... });

test("idle state with last_cycle_at=null renders 'Idle - awaiting first cycle'", () => { ... });

test("transitions between active and idle do not render a skeleton or shimmer", () => { ... });

test("uses REST snapshot for initial paint, no idle flash before first SSE frame", () => { ... });

test("applies .research-active class on active container", () => { ... });

test("applies .researching-dot class on the indicator", () => { ... });

test("applies Researching badge variant via shared Badge component", () => { ... });

test("does not define any new CSS custom properties", () => { ... });

test("description renders with line-clamp-1 class and full text in accessible name", () => { ... });

test("respects prefers-reduced-motion (asserts no inline animation override)", () => { ... });

test("link is keyboard-focusable with focusRing utility classes", () => { ... });

test("role='status' and aria-live='polite' on banner element", () => { ... });

test("aria-live debounce: 2 transitions within 500ms yield 1 announce", () => { ... });

test("status='fallback' renders quiet '(reconnecting)' hint without destructive alert", () => { ... });
```

Mock `useLiveResearch` per-test using `vi.mock("@/lib/use-live-research", ...)`. Use Testing Library `render`, `screen`, `act`, and `userEvent` (already in the repo).

### Step 2: Confirm Red
```bash
cd frontend && pnpm test tests/live-research-banner.test.tsx
```

All 18 tests must FAIL with `Cannot find module '@/components/app/live-research-banner'`.

## Verification Commands

```bash
cd frontend && pnpm test tests/live-research-banner.test.tsx
# Expected: 18 FAILED tests, module not found
```

## Success Criteria

- 18 vitest cases added, all FAIL for the intended reason.
- Mock `useLiveResearch` to drive each rendering scenario without the real hook.
- Tests assert on accessible queries (`getByRole`, `getByText`) where possible, falling back to data-testid only for the indicator dot and the "+N more in flight" suffix.
- No production code created in this task.
