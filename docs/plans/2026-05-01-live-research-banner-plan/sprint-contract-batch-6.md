# Sprint Contract — Batch 6 (Frontend Hook + Banner)

**Plan:** `docs/plans/2026-05-01-live-research-banner-plan/`
**Batch:** 6 of 7
**Mode:** Two Red/Green pairs (011a → 011b → 012a → 012b — sequential because 012b needs 011b)
**Code checklist:** `docs/retros/checklists/code-v1.md` (v1)

## Tasks in this batch

| Plan ID | TaskList ID | Subject | Depends-on |
|---|---|---|---|
| 011a | 16 | useLiveResearch hook tests — Red | 010 ✓ |
| 011b | 17 | useLiveResearch hook — Green | 011a |
| 012a | 18 | LiveResearchBanner component tests — Red | 010 ✓ |
| 012b | 19 | LiveResearchBanner component — Green | 012a, 011b |

## Acceptance Criteria

### Task 011a — Hook tests (Red, 14 cases)
- File `frontend/tests/use-live-research.test.ts` created with 14 vitest cases.
- File `frontend/tests/__helpers__/mock-event-source.ts` created with `MockEventSource` stub class.
- `MockEventSource` installed as `globalThis.EventSource` via `frontend/vitest.setup.ts` (or per-test in `beforeEach`).
- Tests use `vi.useFakeTimers()` for time-based assertions.
- Tests cover: mount opens EventSource, status loading→open, snapshot/research_started/research_ended event handling, 3 consecutive errors → fallback, 10 s REST poll cadence, 60 s SSE re-open probe in fallback, first successful snapshot after fallback cancels REST polling, unmount cleanup, StrictMode double-mount safe, no Last-Event-ID reuse.
- All 14 tests FAIL with `Cannot find module '@/lib/use-live-research'`.
- No production code created.

### Task 011b — Hook impl (Green)
- File `frontend/lib/use-live-research.ts` created (~60 LOC).
- Exports `useLiveResearch(): UseLiveResearchResult` and `LiveResearchStatus` type.
- Single `useEffect` owns subscription lifecycle (StrictMode-safe).
- `useRef` for EventSource, AbortController, error counter, interval handles.
- State: snapshot + status only.
- Does NOT send a `Last-Event-ID` header on reconnect (native `EventSource` ignores it; documented in code).
- `research_started` dedupes by `problem_id`.
- `research_ended` removes from active and updates `snapshot.last_cycle_at`.
- REST fallback uses `fetchLiveResearchSnapshot(controller.signal)` from task 010.
- 14/14 tests PASS.
- `pnpm tsc --noEmit` and `pnpm lint` exit 0.

### Task 012a — Component tests (Red, 18 cases)
- File `frontend/tests/live-research-banner.test.tsx` created.
- Tests mock `useLiveResearch` via `vi.mock("@/lib/use-live-research", ...)`.
- Use Testing Library's `render`, `screen`, `act`, `userEvent`.
- Tests cover: active rendering (title, count, confidence%, sublabel), link to `/memories/{id}`, multi-problem foregrounding + "+N more in flight", idle copy variants ("Idle - last cycle Xm ago" / "Idle - awaiting first cycle"), no skeleton/shimmer on transitions, REST initial paint, `.research-active` + `.researching-dot` classes + `Researching` badge variant, no new CSS tokens, line-clamp-1 + full description in accessible name, prefers-reduced-motion respect, focusRing keyboard focus, `role="status"` + `aria-live="polite"`, aria-live debounce (1 s), `(reconnecting)` hint when `status === "fallback"`.
- All 18 tests FAIL with `Cannot find module '@/components/app/live-research-banner'`.
- No production code created.

### Task 012b — Component impl (Green, ~120 LOC)
- File `frontend/components/app/live-research-banner.tsx` created.
- Exports `LiveResearchBanner` component with `LiveResearchBannerProps` (optional `initialSnapshot`).
- Apply `.research-active` on outer Card.
- Apply `.researching-dot` on indicator.
- Use `<Badge variant="researching">Researching</Badge>` (NOT a custom badge).
- Dynamic import `TitleMarkdown` (mirror `page.tsx:81-94`).
- `getRelativeTime(active.research_started_at)` for sublabel; tick on 1 s interval.
- Idle: `getRelativeTime(snapshot.last_cycle_at)` for "Xm ago"; null → "Idle - awaiting first cycle".
- Multi-problem: foreground `snapshot.active[0]` (already DESC-ordered) + `+{N-1} more in flight` suffix.
- A11y: `<aside role="status" aria-live="polite" aria-atomic="false" aria-label="Live research status">`.
- Aria-live debounce: 1 s.
- Fallback hint: quiet `(reconnecting)` text after title.
- `React.memo` applied.
- 18/18 tests PASS.
- `pnpm tsc --noEmit` and `pnpm lint` exit 0.
- No new CSS custom properties (verify via grep).
- No new dependency.

## Code checklist v1 — items most relevant this batch

- **CODE-ASSUME-01 / 02**: BEFORE authoring, grep for: `Badge`, `Card`, `TitleMarkdown`, `focusRing`, `getRelativeTime`, `getConfidenceTier`, `cn`, `useTicker`, `Researching` (badge variant). Verify each one's exact export name + path.
- **CODE-EDIT-01**: re-Read after Biome reformats the test/setup files.
- **CODE-LINT-01**: `pnpm lint` (Biome + tsc) at end of each task.
- **CODE-TEST-01**: tests use mocked EventSource + `vi.mock` for the hook in component tests — no real network.
- **CODE-TEST-03**: Red FAILures must be "module not found", not config/syntax errors.
- **CODE-A11Y-01**: any `aria-*` attributes need supported roles. The aside-with-`role="status"` pattern is OK; verify Biome's `useAriaPropsSupportedByRole` rule is satisfied.
- **CODE-VERIFY-01**: full backend `make fast` should still be 466 passing. Frontend `pnpm test` should add 14 + 18 = 32 new vitest cases.
- **CODE-SCOPE-01**: 011a touches only `tests/use-live-research.test.ts` + `tests/__helpers__/mock-event-source.ts` + (optionally) `vitest.setup.ts`; 011b touches only `lib/use-live-research.ts`; 012a touches only `tests/live-research-banner.test.tsx`; 012b touches only `components/app/live-research-banner.tsx`.

## Out-of-scope guards

- Do NOT wire the banner into `frontend/app/page.tsx` — that's task 013.
- Do NOT add new CSS tokens.
- Do NOT add a new dependency to `frontend/package.json`.
- Do NOT touch any backend file.
- Do NOT use `<Alert>` for the (reconnecting) hint — quiet text only per calm-tone constraint.

## Verification commands (per task)

### Task 011a
```bash
cd frontend && pnpm test tests/use-live-research.test.ts
# Expected: 14 FAILED, module not found
```

### Task 011b
```bash
cd frontend && pnpm test tests/use-live-research.test.ts
# Expected: 14 PASSED
cd frontend && pnpm tsc --noEmit
cd frontend && pnpm lint
```

### Task 012a
```bash
cd frontend && pnpm test tests/live-research-banner.test.tsx
# Expected: 18 FAILED, module not found
```

### Task 012b
```bash
cd frontend && pnpm test tests/live-research-banner.test.tsx
# Expected: 18 PASSED
cd frontend && pnpm tsc --noEmit
cd frontend && pnpm lint
```

### Full-batch regression
```bash
cd frontend && pnpm test
# Expected: prior cases + 14 + 18 PASSED
make fast
# Expected: still 466 (no backend changes)
```
