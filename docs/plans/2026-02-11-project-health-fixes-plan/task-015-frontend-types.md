# Task 015: Add Frontend Type Safety

**Area**: Frontend
**Priority**: Low
**BDD Scenario**: Only valid statuses are allowed (ref: Scenario 1)

## Objective

Add union type for review status to ensure type safety.

## Files to Modify

- `web/lib/types.ts`

## What to Implement

### Add ReviewStatus Union Type

```typescript
export type ReviewStatus = "approved" | "pending" | "rejected" | "error";

export type ThreadListItem = {
  thread_id: string;
  title: string;
  body_preview: string;
  tags: string[];
  review_status: ReviewStatus;
  created_at: string;
};

export type ThreadDetail = {
  thread_id: string;
  title: string;
  body: string;
  tags: string[];
  error_log: string | null;
  environment: Record<string, string> | null;
  review_status: ReviewStatus;
  created_at: string;
  comments: CommentDetail[];
};

export type CommentDetail = {
  comment_id: string;
  thread_id: string;
  content: string;
  is_solution: boolean;
  review_status: ReviewStatus;
  created_at: string;
};
```

## Verification

```bash
cd web && pnpm build
```

Expected: TypeScript compilation succeeds with no errors.

## Dependencies

None - independent type change

## BDD References

- Feature: Review status is type-safe - Scenario 1