# Task 015b: Frontend /memories route plus 308 redirects — Green

**depends-on**: 015a

## Description

Move `frontend/app/problems/` to `frontend/app/memories/`. Add 308 redirect rules in `frontend/next.config.mjs`. Update in-repo links. Update page copy from "Problems" to "Memories" on list and detail pages; keep backend REST paths (`/v1/problems`) untouched — only the frontend surface renames.

## Execution Context

**Task Number**: 015b of 41
**Phase**: Frontend reorg
**Prerequisites**: Task 015a red tests committed.

## BDD Scenario

(Same as task 015a — see `bdd-specs.md`.)

## Files to Modify/Create

- Move: `frontend/app/problems/page.tsx` → `frontend/app/memories/page.tsx`.
- Move: `frontend/app/problems/[id]/*` → `frontend/app/memories/[id]/*`.
- Modify: `frontend/next.config.mjs` — add `redirects()` function.
- Modify: `frontend/app/layout.tsx` — add top nav linking to `/memories`, `/research`, `/health`.
- Modify: `frontend/app/page.tsx` — redirect root to `/memories` via `redirect("/memories")` (Next.js App Router helper).
- Update all in-repo `Link href="/problems"` → `/memories`.

## Steps

### Step 1: Route move
- Use `git mv` so history is preserved. Verify TypeScript compiles (`pnpm tsc --noEmit`).

### Step 2: next.config.mjs redirects
```js
async redirects() {
  return [
    {
      source: "/problems",
      destination: "/memories",
      permanent: true,
      // Next.js maps permanent: true to 308
    },
    {
      source: "/problems/:id",
      destination: "/memories/:id",
      permanent: true,
    },
  ];
}
```

### Step 3: Nav + copy
- `layout.tsx` adds a simple nav bar: Memories | Research | Health (Research and Health are implemented in later tasks; link to placeholder routes that will render once their tasks land).
- Update heading text: "Problems" → "Memories", "Problem" → "Memory".

### Step 4: Green
- `cd frontend && pnpm test tests/routes-redirect.test.ts`
- `cd frontend && pnpm build` — confirm the build succeeds with redirects configured.

## Verification Commands

```bash
cd frontend && pnpm lint && pnpm test && pnpm build
```

## Success Criteria

- All 015a scenarios pass.
- `pnpm build` emits the 308 redirect rules for `/problems` and `/problems/:id`.
- Legacy direct-link e.g. `/problems/abc` hits 308 → `/memories/abc`.
