# Task 016: Add Frontend ARIA Live Regions

**Area**: Frontend
**Priority**: Low
**BDD Scenario**: Role check loading is announced, Thread loading is announced

## Objective

Add ARIA live regions to loading states for screen reader announcements.

## Files to Modify

- `web/app/page.tsx`
- `web/app/threads/[id]/page.tsx`

## What to Implement

### Home Page (page.tsx)

Update loading state:
- Add `role="status"` attribute
- Add `aria-live="polite"` attribute

Example:
```tsx
<p role="status" aria-live="polite">Checking your role...</p>
```

### Thread Detail Page (threads/[id]/page.tsx)

Update loading state:
- Add `role="status"` attribute
- Add `aria-live="polite"` attribute

## Verification

```bash
cd web && pnpm build
```

Expected: Build succeeds. Manual verification with screen reader or aXe extension.

## Dependencies

- Task 015 (labels done)
