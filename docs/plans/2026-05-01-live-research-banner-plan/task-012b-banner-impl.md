# Task 012b: <LiveResearchBanner/> component — Green

**depends-on**: 012a, 011b

## Description

Implement `frontend/components/app/live-research-banner.tsx`. The component consumes `useLiveResearch`, renders the active state via reused primitives (`Card` shell with `research-active` class, `Badge variant="researching"`, `TitleMarkdown` dynamic-imported, `getRelativeTime` for sublabel), or the idle state with calm copy. ~120 LOC.

## Execution Context

**Task Number**: 012b of 20
**Phase**: Frontend — Component Green
**Prerequisites**: Task 012a (failing tests), Task 011b (hook implementation).

## BDD Scenario

(Same scenarios as 012a — this task makes the 18 tests PASS.)

## Files to Modify/Create

- Create: `frontend/components/app/live-research-banner.tsx`

## Steps

### Step 1: Implement the component

Public contract (signatures only):

```typescript
"use client";

import { type ReactElement } from "react";

export type LiveResearchBannerProps = {
  /** Optional REST snapshot to use for initial paint. Lets a server
   *  component pre-fetch the snapshot to avoid an idle->active flash. */
  initialSnapshot?: import("@/lib/types").LiveResearchSnapshot | null;
};

/**
 * The hero-bottom banner showing live research state.
 *
 * Active state: <Researching> badge + most-recently-started problem title
 * (linked, focusRing) + solution_count + confidence percent badge +
 * "started Xs ago" sublabel + optional "+N more in flight" suffix.
 *
 * Idle state: "Idle · last cycle Xm ago" (or "Idle · awaiting first cycle"
 * when last_cycle_at is null).
 *
 * Fallback state: same as last-known visible state plus a quiet
 * "(reconnecting)" hint.
 */
export function LiveResearchBanner(
  props: LiveResearchBannerProps,
): ReactElement { ... }
```

Implementation rules:

- Apply `.research-active` class on the outer Card surface (inherits the existing pulse glow + reduced-motion fallback automatically).
- Apply `.researching-dot` class on the leading indicator.
- Use `<Badge variant="researching">Researching</Badge>` — never a custom badge.
- Use `dynamic(() => import("@/components/app/title-markdown")...)` for the title (mirror `page.tsx:81-94`).
- Use `getRelativeTime(active.research_started_at)` for the sublabel; treat the timestamp as live by re-rendering on a 1 s tick (use `useTicker` if it exists, else a tiny inline `setInterval` cleared on unmount).
- Idle: `getRelativeTime(snapshot.last_cycle_at)` for the "Xm ago" string; null → `"Idle · awaiting first cycle"`.
- Multi-problem: foreground `snapshot.active[0]` (which is already DESC-ordered server-side) and render a quiet `+{snapshot.active.length - 1} more in flight` text suffix.
- A11y: `<aside role="status" aria-live="polite" aria-atomic="false" aria-label="Live research status">` wrapper.
- Aria-live debounce: implement a 1 s debounce on the announcement region (e.g., a hidden `<span aria-live="polite">` whose text updates only after a `setTimeout(1000)`).
- Fallback hint: when hook returns `status === "fallback"`, render a quiet text `(reconnecting)` after the title — no `<Alert>` (per design's calm-tone constraint).
- React.memo the component, keyed implicitly by `snapshot` reference.

### Step 2: Run tests to confirm Green
```bash
cd frontend && pnpm test tests/live-research-banner.test.tsx
```

All 18 tests must PASS.

### Step 3: Type-check + lint
```bash
cd frontend && pnpm tsc --noEmit
cd frontend && pnpm lint
```

## Verification Commands

```bash
cd frontend && pnpm test tests/live-research-banner.test.tsx
cd frontend && pnpm tsc --noEmit
cd frontend && pnpm lint
```

## Success Criteria

- 18/18 tests pass.
- Component reuses `Badge variant="researching"`, `Card`, `.research-active`, `.researching-dot`, `TitleMarkdown`, `focusRing`, `getRelativeTime`, `getConfidenceTier`, `cn`.
- No new CSS tokens introduced (verify via `grep -r "var(--research-" frontend/components/app/live-research-banner.tsx` shows only existing token names).
- `aria-live` announcements debounced by 1 s.
- React.memo applied to avoid re-rendering on unrelated parent updates.
- No new dependency added.
- Biome lint passes.
