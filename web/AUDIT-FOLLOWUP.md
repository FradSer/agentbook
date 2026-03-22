# Audit follow-up tasks (`web/`)

Tracks fixes aligned with the suggested slash-style workstreams. Update status as you complete items.

## Status legend

- **done**: Implemented in tree
- **partial**: Some work landed; more possible
- **open**: Not started or needs product/design input

| Command / area | Addresses | Status | Notes |
|----------------|-----------|--------|-------|
| **/harden** | Tab pattern (C1), headings (H3–H4), decorative `aria-hidden` (L1), edge cases | **done** | Tabs + keyboard; Human `h1`; solution markdown headings; nav mark; **`CardTitle as="h2"`** on home problem cards |
| **/polish** | Focus rings (H1–H2), visual consistency | **done** | Shared [`focusRing`](./lib/focus-ring.ts) on nav links, home card links, human tab buttons |
| **/normalize** | Tokens vs raw hex (M2–M3), contrast tokens (M1) | **done** | Theme tokens + **`--avatar-preset-*-from/to`** in `@theme`; `getAgentAvatar` returns `var(--avatar-preset-n-*)` |
| **/optimize** | Markdown cost (M5), bundle (L2), motion (M6) | **partial** | `optimizePackageImports`; `memo` on `ProblemCard`; **`dynamic()`** `TitleMarkdown` on home; reduced-motion on glow |
| **/adapt** | Tab strip scroll discoverability (L3) | **done** | Thin scrollbar, snap, SR hint, **`sm:hidden` “Scroll sideways”** line |
| **/quieter** | Glow/glass intensity | **partial** | Prior pass on globals/cards; **ID line** uses `font-sans tabular-nums` instead of mono |
| **/critique** or **frontend-design** | Deliberate aesthetic direction | **partial** | **[`../.impeccable.md`](../.impeccable.md)** documents audience, use cases, tone, constraints; full visual re-theme still optional |

## Checklist (actionable)

### Hardening

- [x] ARIA tabs + keyboard
- [x] Page-level `h1` on Human dashboard
- [x] Solution markdown heading levels under page title
- [x] Decorative nav icon `aria-hidden`
- [x] `CardTitle` as `h2` on home problem cards (inside card link)

### Polish

- [x] Focus rings via shared `focusRing` helper
- [x] Unify focus ring on nav, home card `Link`, human tabs

### Normalize

- [x] `body` / layout background foreground tokens
- [x] Brand mark + **avatar** gradients in `@theme` (`--avatar-preset-0-from` … `--avatar-preset-7-to`)

### Optimize

- [x] `experimental.optimizePackageImports` (incl. `remark-gfm`)
- [x] `React.memo` on home `ProblemCard`
- [x] `next/dynamic` for `TitleMarkdown` on home list
- [ ] Optional: virtualize `.problem-grid` if lists regularly exceed ~50 items

### Adapt

- [x] Tab strip: scrollbar, snap, SR + **visible mobile hint**

### Quieter

- [x] Softer glows, glass blur, coral primary, flat cards
- [x] Problem list ID line: sans + tabular nums (quieter than mono)

### Direction (critique / frontend-design)

- [x] Design context: [`.impeccable.md`](../.impeccable.md) at repo root
- [ ] Choose and apply a bolder aesthetic direction (typography, color story, patterns) when ready

## Verification

```bash
cd web && pnpm lint && pnpm test && pnpm build
```
