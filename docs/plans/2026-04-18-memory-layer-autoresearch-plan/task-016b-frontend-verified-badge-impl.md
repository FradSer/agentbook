# Task 016b: Frontend verified badge and dual score — Green

**depends-on**: 016a

## Description

Add `<VerifiedPill>` component (coral accent, `aria-label="sandbox verified"`) rendered when any outcome has `kind === "verified"`. Add `<DualScore>` showing global `best_confidence` and the highest per-environment score on the detail page. Use tokens from `frontend/app/globals.css` — do not introduce new hex values (per `.impeccable.md` single-accent rule).

## Execution Context

**Task Number**: 016b of 41
**Phase**: Frontend reorg
**Prerequisites**: Task 016a red tests committed.

## BDD Scenario

(Same three scenarios as task 016a — see `bdd-specs.md`.)

## Files to Modify/Create

- Create: `frontend/app/memories/_components/verified-pill.tsx`
- Create: `frontend/app/memories/_components/dual-score.tsx`
- Modify: `frontend/app/memories/page.tsx` — render `<VerifiedPill>` per row when applicable.
- Modify: `frontend/app/memories/[id]/page.tsx` — render `<DualScore>` in the header section.
- Modify: `frontend/lib/types.ts` — extend `Outcome` / `TimelineEntry` types with `kind?: "verified" | "observed"`.

## Steps

### Step 1: Types
- Add `kind?: "verified" | "observed"` to the relevant TypeScript types. Do not make it required — during the migration window an outcome may omit the field.

### Step 2: VerifiedPill component
- Signature:
  ```ts
  export function VerifiedPill({ size = "sm" }: { size?: "sm" | "md" }): JSX.Element;
  ```
- Render a span with coral background (`bg-[var(--accent-coral)]`), text "Verified", `aria-label="sandbox verified"`. No icon, no emoji.

### Step 3: DualScore component
- Signature:
  ```ts
  export function DualScore({
    global,
    perEnvironment,
  }: {
    global: number;
    perEnvironment: Record<string, number> | null;
  }): JSX.Element;
  ```
- Render two numbers: the global score with label "Global", and the max per-environment score with its environment key label (e.g. "os=ubuntu-22"). If `perEnvironment` is null or empty, render only the global score.

### Step 4: Page integration
- List page: iterate memories; render `<VerifiedPill>` when `memory.has_verified_outcomes === true`. The backend already returns enough data; if not, add a derived boolean in the API response (falls back to computing client-side from outcome list).
- Detail page: render `<DualScore>` in the card header above the solutions list.

### Step 5: Green
- `cd frontend && pnpm test tests/memories-verified-badge.test.tsx`
- `cd frontend && pnpm lint && pnpm build`

## Verification Commands

```bash
cd frontend && pnpm lint && pnpm test && pnpm build
```

## Success Criteria

- All 016a scenarios pass.
- Single-accent rule respected (no new colours).
- Component tests run in jsdom without needing a running backend.
