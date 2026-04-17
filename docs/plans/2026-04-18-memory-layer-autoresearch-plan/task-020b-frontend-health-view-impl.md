# Task 020b: Frontend /health view — Green

**depends-on**: 020a

## Description

Implement `frontend/app/health/page.tsx` as a server component (data fetched server-side for freshness + no client-side fetch). Read-only panels: sandbox pass rate, cluster alerts, circuit-breaker state, counters. No inputs, no buttons that mutate.

## Execution Context

**Task Number**: 020b of 41
**Phase**: Frontend reorg
**Prerequisites**: Task 020a red tests committed.

## BDD Scenario

(Same as task 020a — see `bdd-specs.md`.)

## Files to Modify/Create

- Create: `frontend/app/health/page.tsx`
- Create: `frontend/app/health/_components/metric-card.tsx`
- Create: `frontend/app/health/_components/circuit-pill.tsx`

## Steps

### Step 1: Page component
- Server component: `async function HealthPage()` fetches `/v1/health-metrics` with `next: { revalidate: 30 }` (matches backend cache TTL).

### Step 2: MetricCard
- Signature:
  ```ts
  export function MetricCard({
    label,
    value,
    unit,
  }: {
    label: string;
    value: number | string;
    unit?: string;
  }): JSX.Element;
  ```
- Render a large value + small label in the existing grid style used on the homepage/radar view.

### Step 3: CircuitPill
- Signature:
  ```ts
  export function CircuitPill({
    state,
    openedAt,
  }: {
    state: "closed" | "open" | "probing";
    openedAt: string | null;
  }): JSX.Element;
  ```
- Closed: dim neutral pill. Open: coral pill with "Sandbox circuit OPEN" and relative time. Probing: dimmer coral with "Probing".

### Step 4: Green
- `cd frontend && pnpm test tests/health-view.test.tsx && pnpm lint && pnpm build`.

## Verification Commands

```bash
cd frontend && pnpm lint && pnpm test && pnpm build
```

## Success Criteria

- All 020a scenarios pass.
- Page is a server component (no client `fetch` flash).
- No write surfaces in the DOM.
