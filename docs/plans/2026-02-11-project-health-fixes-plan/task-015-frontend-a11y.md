# Task 015: Add Frontend Accessibility Labels

**Area**: Frontend
**Priority**: Medium
**BDD Scenario**: Search input has label, API key input has label, Model type input has label

## Objective

Add accessible labels to form inputs.

## Files to Modify

- `web/app/register/page.tsx`
- `web/app/agent/page.tsx`
- `web/components/thread/search-bar.tsx`

## What to Implement

### Register Page (register/page.tsx)

Add `<Label>` component for model type input:
- Wrap input in div with Label
- Use `htmlFor` attribute matching input `id`

### Agent Page (agent/page.tsx)

Add labels for all form inputs:
- API key input
- Any other inputs present

### Search Bar (search-bar.tsx)

Add visually hidden label for search input:
- Use `<Label className="sr-only">` pattern
- Or add `aria-label` attribute directly

## Verification

```bash
cd web && pnpm build
```

Expected: Build succeeds. Manual verification with browser dev tools to confirm label associations.

## Dependencies

- Task 014 (types done)
