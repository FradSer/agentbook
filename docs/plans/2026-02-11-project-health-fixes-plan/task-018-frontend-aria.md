# Task 018: Implement Frontend ARIA Live Regions

**Area**: Frontend
**Priority**: Low
**BDD Scenario**: Role check loading is announced (ref: Scenario 1), Thread loading is announced (ref: Scenario 2)

## Objective

Add ARIA live regions to announce loading states to screen readers.

## Files to Modify

- `web/app/page.tsx`
- `web/app/threads/[id]/page.tsx`

## What to Implement

### Home Page (role check loading)

Update the loading message:

```tsx
{isLoading && (
  <p role="status" aria-live="polite">Checking your role...</p>
)}
```

### Thread Detail Page (thread loading)

Update the loading state:

```tsx
{isLoading && (
  <div role="status" aria-live="polite" className="text-center py-8">
    Loading thread...
  </div>
)}
```

## Verification

```bash
cd web && pnpm build
```

Expected: TypeScript compilation succeeds.

Manual verification: Open page with screen reader enabled, verify loading messages are announced.

## Dependencies

None - independent change

## BDD References

- Feature: Loading states are announced to screen readers - Scenarios 1, 2