# Task 018b: Frontend /research view — Green

**depends-on**: 018a

## Description

Implement `frontend/app/research/page.tsx` as a client component that fetches `/v1/research-activity` and renders an expandable timeline. Match the visual language of `.impeccable.md` — quiet, coral accent only when confidence delta is positive.

## Execution Context

**Task Number**: 018b of 41
**Phase**: Frontend reorg
**Prerequisites**: Task 018a red tests committed.

## BDD Scenario

(Same as task 018a — see `bdd-specs.md`.)

## Files to Modify/Create

- Create: `frontend/app/research/page.tsx`
- Create: `frontend/app/research/_components/cycle-card.tsx`
- Create: `frontend/app/research/_components/sandbox-detail.tsx`

## Steps

### Step 1: Page component
- Read `memory_id` from `useSearchParams`. If absent, render empty-state copy linking to `/memories` with a note: "Pick a memory to see its hill-climbing history".

### Step 2: Fetch + state
- SWR or native `fetch` with `use` hook (Next 16 App Router). Loading skeleton for 200ms; error shows a terse error banner with retry.

### Step 3: CycleCard
- Signature:
  ```ts
  export function CycleCard({
    cycle,
  }: {
    cycle: ResearchActivityItem;
  }): JSX.Element;
  ```
- Shows `created_at` relative time, `status`, confidence delta (`new_confidence - previous_best_confidence`). If `cycle.sandbox_run` exists, render an expand control that toggles the `<SandboxDetail>` block.

### Step 4: SandboxDetail
- Signature:
  ```ts
  export function SandboxDetail({
    run,
  }: {
    run: { success: boolean; stdout: string; stderr: string; exit_code: number };
  }): JSX.Element;
  ```
- Two collapsible `<pre>` blocks (stdout, stderr) plus `exit_code` + pass/fail badge.

### Step 5: Green
- `cd frontend && pnpm test tests/research-view.test.tsx && pnpm lint && pnpm build`.

## Verification Commands

```bash
cd frontend && pnpm lint && pnpm test && pnpm build
```

## Success Criteria

- All 018a scenarios pass.
- `/research?memory_id=<known id>` page loads end-to-end against a running backend (manual smoke verified).
- No new design tokens introduced.
