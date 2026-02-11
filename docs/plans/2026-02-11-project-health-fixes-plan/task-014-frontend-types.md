# Task 014: Add Frontend Type Safety

**Area**: Frontend
**Priority**: Medium
**BDD Scenario**: Only valid statuses are allowed

## Objective

Create union type for ReviewStatus to improve type safety.

## Files to Modify

- `web/lib/types.ts`

## What to Implement

### Add ReviewStatus Union Type

1. Add new type export:
```typescript
export type ReviewStatus = "approved" | "pending" | "rejected" | "error";
```

2. Update existing types to use `ReviewStatus`:
- `ThreadListItem.review_status: ReviewStatus`
- `ThreadDetail.review_status: ReviewStatus`
- `CommentDetail.review_status: ReviewStatus`

## Verification

```bash
cd web && pnpm build
```

Expected: Build succeeds with no type errors.

## Dependencies

- Task 013 (backend config done)
