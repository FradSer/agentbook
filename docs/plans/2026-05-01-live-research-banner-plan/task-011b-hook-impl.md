# Task 011b: useLiveResearch hook — Green

**depends-on**: 011a

## Description

Implement `frontend/lib/use-live-research.ts`. The hook owns one `EventSource`, parses `snapshot` / `research_started` / `research_ended` events into a `LiveResearchSnapshot` state, exposes `status: "loading" | "open" | "fallback" | "error"`, and falls back to REST polling after 3 consecutive errors with a 60-second SSE re-open probe. ~60 LOC.

## Execution Context

**Task Number**: 011b of 20
**Phase**: Frontend — Hook Green
**Prerequisites**: Task 011a (failing tests).

## BDD Scenario

(Same as 011a — this task makes the 14 tests PASS.)

## Files to Modify/Create

- Create: `frontend/lib/use-live-research.ts`

## Steps

### Step 1: Implement the hook

Public contract (signatures only):

```typescript
import type { LiveResearchSnapshot } from "@/lib/types";

export type LiveResearchStatus = "loading" | "open" | "fallback" | "error";

export type UseLiveResearchResult = {
  snapshot: LiveResearchSnapshot | null;
  status: LiveResearchStatus;
};

/**
 * Subscribes to the live research SSE stream, with REST snapshot fallback.
 *
 * Behaviour:
 * - On mount: opens EventSource at `${API_BASE_URL}/v1/dashboard/research/stream`.
 * - On `snapshot` event: replaces full state.
 * - On `research_started`: appends to active list (deduped by problem_id).
 * - On `research_ended`: removes from active list and updates last_cycle_at.
 * - On 3 consecutive `onerror` without an intervening message: switches to
 *   REST polling at /v1/dashboard/research/live every 10 s, sets status
 *   to "fallback", and tries to re-open the EventSource every 60 s.
 * - On the first successful snapshot after fallback: cancels REST interval
 *   and returns to "open".
 * - On unmount: closes EventSource, aborts pending fetch, clears intervals.
 */
export function useLiveResearch(): UseLiveResearchResult { ... }
```

Implementation rules:

- One `useEffect` that owns all subscriptions; cleanup closes everything (StrictMode-safe).
- Use `useRef` for the `EventSource`, the `AbortController`, the error counter, and the two interval handles. State is only the snapshot + status.
- Do NOT send a `Last-Event-ID` header on reconnect (native `EventSource` ignores it; this is documented to ensure no future patch tries to honour it).
- The `research_started` handler MUST dedupe by `problem_id` so a duplicate event doesn't double-add.
- `research_ended` handler updates `snapshot.last_cycle_at` from the event's payload.
- REST fallback uses `fetchLiveResearchSnapshot(controller.signal)` from task 010.

### Step 2: Run tests to confirm Green
```bash
cd frontend && pnpm test tests/use-live-research.test.ts
```

All 14 tests must PASS.

### Step 3: Type-check + lint
```bash
cd frontend && pnpm tsc --noEmit
cd frontend && pnpm lint
```

## Verification Commands

```bash
cd frontend && pnpm test tests/use-live-research.test.ts
cd frontend && pnpm tsc --noEmit
cd frontend && pnpm lint
```

## Success Criteria

- 14/14 tests pass.
- Hook is ~60 LOC, no inline implementation in the component.
- Single `useEffect` owns the subscription lifecycle.
- StrictMode double-mount test passes (no leaked connections).
- No new dependency added.
