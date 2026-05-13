# Task 010: Frontend types and fetchLiveResearchSnapshot helper

**depends-on**: 006

## Description

Add the TypeScript types mirroring the Pydantic schemas from task 006, plus the `fetchLiveResearchSnapshot()` API helper modelled after the existing `fetchRadar` / `fetchMetrics` style. Foundation task — no test pair (the helper is exercised by the hook tests in 011a).

## Execution Context

**Task Number**: 010 of 20
**Phase**: Frontend — Foundation
**Prerequisites**: Task 006 (backend schema fixes the contract).

## BDD Scenario

The types underwrite every frontend assertion — no isolated scenario. Spec source: `../2026-05-01-live-research-banner-design/bdd-specs.md`.

## Files to Modify/Create

- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`

## Steps

### Step 1: Add types

In `frontend/lib/types.ts`:

```typescript
export type LiveResearchActive = {
  problem_id: string;
  description: string;
  solution_count: number;
  best_confidence: number;
  research_started_at: string;   // ISO 8601 UTC
  elapsed_seconds: number;
};

export type LiveResearchSnapshot = {
  active: LiveResearchActive[];
  last_cycle_at: string | null;  // ISO 8601 UTC or null
  now: string;                   // ISO 8601 UTC
};
```

### Step 2: Add the fetcher

In `frontend/lib/api.ts`, mirror the style of `fetchRadar` (lines 67-73):

```typescript
import type { LiveResearchSnapshot } from "@/lib/types";

export async function fetchLiveResearchSnapshot(
  signal?: AbortSignal,
): Promise<LiveResearchSnapshot> {
  return request<LiveResearchSnapshot>(
    "/v1/dashboard/research/live",
    { signal },
  );
}
```

The `signal` parameter is an `AbortController.signal` so the hook can cancel an in-flight fetch on unmount or on SSE recovery. The existing `request<T>` helper passes `cache: "no-store"` already.

### Step 3: Re-verify type checks
```bash
cd frontend && pnpm tsc --noEmit
```

### Step 4: Run lint
```bash
cd frontend && pnpm lint
```

## Verification Commands

```bash
cd frontend && pnpm tsc --noEmit
cd frontend && pnpm lint
```

## Success Criteria

- Both types exported from `frontend/lib/types.ts`.
- `fetchLiveResearchSnapshot` accepts an optional `AbortSignal` and returns `Promise<LiveResearchSnapshot>`.
- `tsc --noEmit` passes with zero errors.
- Biome lint passes.
- No new dependency added.
