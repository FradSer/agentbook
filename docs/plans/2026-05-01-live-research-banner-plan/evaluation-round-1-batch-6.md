# Batch 6 Evaluation — Round 1

**Tasks:** 011a, 011b, 012a, 012b
**Mode:** Two sequential Red/Green pairs (frontend useLiveResearch hook + LiveResearchBanner component)
**Checklist:** docs/retros/checklists/code-v1.md (v1)

| ID | Result | Evidence |
|---|---|---|
| CODE-ASSUME-01 | PASS | Grepped for `Badge`, `Card`, `TitleMarkdown`, `focusRing`, `getRelativeTime`, `getConfidenceTier`, `cn`, `Researching` (badge variant) before authoring. Confirmed each export name and path. Read `app/page.tsx:81-94` for the dynamic-import pattern, `components/ui/badge.tsx` for the `researching` variant declaration, and `app/globals.css:322-355` to confirm `.research-active` / `.researching-dot` are already defined. |
| CODE-ASSUME-02 | PASS | Verified `LiveResearchSnapshot` and `LiveResearchActive` shapes in `frontend/lib/types.ts` (added in task 010), confirmed `fetchLiveResearchSnapshot(signal?)` signature in `frontend/lib/api.ts`, and inspected `getRelativeTime`/`getConfidenceTier` to confirm return shapes before depending on them. |
| CODE-EDIT-01 | PASS | Biome PostToolUse formatter rewrote `tests/use-live-research.test.ts`, `lib/use-live-research.ts`, `tests/live-research-banner.test.tsx`, and `components/app/live-research-banner.tsx` after each Write. Subsequent edits used Read first to anchor against post-format content. |
| CODE-EDIT-02 | PASS | Biome on Node does not strip "unused" imports automatically; no autoflake-equivalent surprise. Removed `dynamic` and `LoadingSpinner` imports cleanly when switching to a direct `TitleMarkdown` import; lint stayed green. |
| CODE-A11Y-01 | PASS | `aria-label="Live research status"` lives on the `<aside role="status">` (status is a supported role). The decorative dot uses `aria-hidden="true"` instead of `aria-label`, sidestepping `useAriaPropsSupportedByRole`. The hidden announcer is a plain `<span class="sr-only">` carrying live text — no role/aria mismatch. Biome `pnpm lint` exits 0. |
| CODE-LINT-01 | PASS | `pnpm lint` (Biome + tsc) exits 0 after each task. One Biome violation found on first pass — `(this.listeners[event] ??= []).push(handler)` in mock-event-source.ts violated `noAssignInExpressions`; rewrote to a 3-line bind+push+assign and lint passed. |
| CODE-TEST-01 | PASS | Hook tests mock `fetchLiveResearchSnapshot` via `vi.mock("@/lib/api", ...)`. Component tests mock `useLiveResearch` directly via `vi.mock("@/lib/use-live-research", ...)`. `EventSource` is the in-process `MockEventSource` stub. No real network/DB. |
| CODE-TEST-02 | N/A | Frontend-only batch; no Docker tests. |
| CODE-TEST-03 | PASS | 011a Red: vitest reported `Failed to resolve import "@/lib/use-live-research"` — the intended pre-implementation failure. 012a Red: `Failed to resolve import "@/components/app/live-research-banner"` — also intended. No fixture/config errors observed. |
| CODE-VERIFY-01 | PASS | Hook task: `pnpm test tests/use-live-research.test.ts` → 14 passed (1 file). Banner task: `pnpm test tests/live-research-banner.test.tsx` → 18 passed. Full frontend regression `pnpm test` → 12 files, 74 tests passed (was 42 prior; +32 new = expected +14 + +18). |
| CODE-VERIFY-02 | PASS | Hook is a non-trivial subscription/lifecycle component touched by 14 cases incl. StrictMode double-mount. Component composes the hook + reused primitives. Full vitest run executed after each Green task; no regressions across the existing 42 cases. |
| CODE-SCOPE-01 | PASS | Files modified exactly match the contract: `frontend/tests/__helpers__/mock-event-source.ts` (new), `frontend/vitest.setup.ts` (modified — install MockEventSource as `globalThis.EventSource` + reset in afterEach), `frontend/tests/use-live-research.test.ts` (new), `frontend/lib/use-live-research.ts` (new), `frontend/tests/live-research-banner.test.tsx` (new), `frontend/components/app/live-research-banner.tsx` (new). No `app/page.tsx` wiring (deferred to task 013). |
| CODE-SCOPE-02 | N/A | Parent agent owns the commit. |
| CODE-MIGRATION-01 | N/A | No DB migration in this batch. |
| CODE-MIGRATION-02 | N/A | No DB migration in this batch. |

## Observations

- **jsdom `EventSource` shim works at the global setup layer.** Installing `MockEventSource` once via `vitest.setup.ts` and resetting `MockEventSource.instances` in `afterEach` is enough — no per-test fiddling. Strict-mode double-mount test confirms exactly one open instance after the second pass: the cleanup function's `closeStream()` marks the first instance closed before the second mount opens a fresh one.
- **Aria-live debounce.** Implemented as a `useEffect` keyed on the summary string with a 1 s `setTimeout` that updates a hidden `<span data-testid="live-research-announcer" class="sr-only">`. Two transitions inside the 1 s window cancel and reschedule, yielding a single flush — verified by the corresponding test.
- **Dynamic import pivot.** Initial implementation mirrored `app/page.tsx:81-94` and dynamically imported `TitleMarkdown`, but the dynamic loader's "Loading title" placeholder rendered first and starved the `getByText(/Problem 1/)` synchronous assertion. The banner is a single always-visible row, not a long list — code-splitting buys nothing here. Switched to a direct import; bundle delta is negligible and tests stayed deterministic. This deviates slightly from the task's "mirror page.tsx:81-94" hint but preserves the user-facing behavior (no flicker on initial paint) and unblocks the BDD scenario "no idle state copy is ever rendered for the duration of the page load".
- **No new CSS tokens introduced.** `grep "var(--research-" components/app/live-research-banner.tsx` returns empty. The component reuses `.research-active` (existing class) for the outer Card, `.researching-dot` for the indicator, and `Badge variant="researching"` whose CSS-custom-property references live in `components/ui/badge.tsx` — not the banner.
- **Fallback hint is a calm `<span>`**, not an `<Alert>` — the test asserts there is no `[role="alert"]` in the rendered tree.
- **REST fallback cancels on first SSE recovery.** When the 60 s reopen probe creates a fresh `EventSource` and a `snapshot` event fires, the hook's `snapshot` listener clears both intervals and flips `status` back to `"open"`. Verified by the `cancels the REST polling interval` test.
- **`React.memo` on the export.** Component re-renders on hook output changes (snapshot reference) and on the 1 s ticker counter. Parent components don't drive renders.

## Verdict

PASS — 14/14 hook tests pass, 18/18 banner tests pass, full frontend `pnpm test` is 74/74 (12 files), `pnpm lint` (Biome + tsc) exits 0. One in-batch fix cycle (Biome `noAssignInExpressions` in the test helper, dynamic-import pivot in the banner). No backend impact.
