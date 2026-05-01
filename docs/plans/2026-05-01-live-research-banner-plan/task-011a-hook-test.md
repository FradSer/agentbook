# Task 011a: useLiveResearch hook (mocked EventSource) — Red

**depends-on**: 010

## Description

Add failing vitest tests for the `useLiveResearch` hook. The hook owns the `EventSource`, parses `snapshot` / `research_started` / `research_ended` events, falls back to REST polling after 3 consecutive errors, and tries to re-open the SSE stream every 60 s while in fallback mode. jsdom does not ship `EventSource`, so the test file installs a small stub class with `addEventListener` and a manual `dispatch` method. Tests must FAIL until task 011b lands.

## Execution Context

**Task Number**: 011a of 20
**Phase**: Frontend — Hook Red
**Prerequisites**: Task 010 (types + API helper).

## BDD Scenario

```gherkin
Scenario: SSE connection drops and the client falls back to REST snapshot
  Given the banner is connected to the SSE stream
  And the banner has rendered problem "P-1"
  When the EventSource emits 3 consecutive onerror events without an onmessage in between
  Then the client switches to polling "/v1/dashboard/research/live" every 10 seconds
  And the banner shows a quiet "(reconnecting)" hint
  And the banner keeps the last-known state visible while polling
  And the client tries to re-open the SSE stream every 60 seconds
  And on the next successful "snapshot" event the polling interval is cancelled
```

**Spec Source**: `../2026-05-01-live-research-banner-design/bdd-specs.md`

## Files to Modify/Create

- Create: `frontend/tests/use-live-research.test.ts`
- Create: `frontend/tests/__helpers__/mock-event-source.ts` (small stub class for jsdom)

## Steps

### Step 1: Write the EventSource stub

In `frontend/tests/__helpers__/mock-event-source.ts`:

```typescript
export class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  readyState = 0;
  listeners: Record<string, ((evt: MessageEvent) => void)[]> = {};
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(event: string, handler: (evt: MessageEvent) => void): void {
    (this.listeners[event] ??= []).push(handler);
  }

  removeEventListener(event: string, handler: (evt: MessageEvent) => void): void {
    this.listeners[event] = (this.listeners[event] ?? []).filter(h => h !== handler);
  }

  close(): void {
    this.closed = true;
  }

  /** Test-only: dispatch a fake SSE message to all listeners. */
  dispatch(event: string, data: unknown): void { ... }

  /** Test-only: simulate a connection error. */
  emitError(): void { ... }
}
```

Stub `globalThis.EventSource = MockEventSource as unknown as typeof EventSource` in `vitest.setup.ts` (or a per-test `beforeEach` if the existing setup is global).

### Step 2: Write failing tests (Red)

Required test contracts in `frontend/tests/use-live-research.test.ts`:

```typescript
test("opens an EventSource at /v1/dashboard/research/stream on mount", () => { ... });

test("status is 'loading' before the first snapshot frame arrives", () => { ... });

test("status is 'open' after the first snapshot event", () => { ... });

test("snapshot state replaces the active list when a snapshot event fires", () => { ... });

test("research_started event adds the problem to active state", () => { ... });

test("research_ended event removes the problem from active state and updates last_cycle_at", () => { ... });

test("3 consecutive onerror events without onmessage trigger REST fallback poll", () => { ... });

test("status switches to 'fallback' when REST polling activates", () => { ... });

test("REST poll fires every 10 seconds in fallback mode", () => { ... });

test("hook tries to re-open EventSource every 60 seconds while in fallback", () => { ... });

test("first successful snapshot event after fallback cancels the REST polling interval", () => { ... });

test("hook closes EventSource and aborts pending fetch on unmount", () => { ... });

test("StrictMode double-mount does not leak a second EventSource", () => { ... });

test("Last-Event-ID is NOT re-sent on reconnect (server re-emits fresh snapshot)", () => { ... });
```

Use `vi.useFakeTimers()` for deterministic interval / 60 s probe assertions. Mock `fetch` for the REST fallback path.

### Step 3: Confirm Red
```bash
cd frontend && pnpm test tests/use-live-research.test.ts
```

All 14 tests must FAIL with `Cannot find module '@/lib/use-live-research'` or similar.

## Verification Commands

```bash
cd frontend && pnpm test tests/use-live-research.test.ts
# Expected: 14 FAILED tests, module not found
```

## Success Criteria

- 14 vitest cases added, all FAIL for the intended reason.
- `MockEventSource` stub installed via `vitest.setup.ts` (no per-test fiddling).
- Fake-timers used for any time-based assertion (10 s poll, 60 s reopen).
- StrictMode double-mount test asserts exactly one live `EventSource` instance.
- No production code created in this task.
