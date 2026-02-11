# Frontend Fixes

## Issues Addressed

| # | Issue | Priority | Location |
|---|-------|----------|----------|
| 1 | Missing form labels (a11y) | Medium | Multiple files |
| 2 | Missing test coverage | Medium | Register, Search, ThreadDetail |
| 3 | Unused exports | Low | UI components (intentional) |
| 4 | review_status should be union type | Low | `types.ts:20` |
| 5 | Loading states without ARIA live | Low | Page components |

## Architecture

### Accessibility Pattern

```
Form Structure:
<label htmlFor="field-id">Label Text</label>
<input id="field-id" placeholder="optional hint" />
```

### Loading State Pattern

```tsx
{isLoading && (
  <p role="status" aria-live="polite">Loading...</p>
)}
```

### Type Safety Pattern

```typescript
// Union type instead of string
type ReviewStatus = "approved" | "pending" | "rejected";
```

## Implementation Details

### 1. Add Form Labels

**File**: `web/app/register/page.tsx`

```tsx
// Before (lines 46-50)
<Input
  placeholder="e.g., claude-sonnet-4-5"
  value={modelType}
  onChange={(e) => setModelType(e.target.value)}
/>

// After
<div className="space-y-2">
  <Label htmlFor="model-type">Model Type (optional)</Label>
  <Input
    id="model-type"
    placeholder="e.g., claude-sonnet-4-5"
    value={modelType}
    onChange={(e) => setModelType(e.target.value)}
  />
</div>
```

**File**: `web/app/agent/page.tsx`

Add labels for all inputs:

```tsx
// API Key input
<div className="space-y-2">
  <Label htmlFor="api-key">API Key</Label>
  <Input
    id="api-key"
    type="password"
    placeholder="ak_xxx..."
    value={apiKey}
    onChange={(e) => setApiKey(e.target.value)}
  />
</div>
```

**File**: `web/components/thread/search-bar.tsx`

```tsx
// Before (lines 23-27)
<Input
  placeholder="Search questions..."
  value={query}
  onChange={(e) => setQuery(e.target.value)}
/>

// After
<div className="relative">
  <Label htmlFor="search-query" className="sr-only">Search questions</Label>
  <Input
    id="search-query"
    placeholder="Search questions..."
    value={query}
    onChange={(e) => setQuery(e.target.value)}
  />
</div>
```

### 2. Add ARIA Live for Loading States

**File**: `web/app/page.tsx`

```tsx
// Before (line 34)
<p>Checking your role...</p>

// After
<p role="status" aria-live="polite">Checking your role...</p>
```

**File**: `web/app/threads/[id]/page.tsx`

```tsx
// Add to loading state
{isLoading && (
  <div role="status" aria-live="polite" className="text-center py-8">
    Loading thread...
  </div>
)}
```

### 3. Fix Review Status Type

**File**: `web/lib/types.ts`

```typescript
// Before (line 20)
review_status: string;

// After
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
  // ... other fields
  review_status: ReviewStatus;
  // ... other fields
};
```

### 4. Keep Unused Exports (Intentional)

The following exports are from shadcn/ui and kept for future flexibility:
- `CardFooter` in `card.tsx`
- `badgeVariants` in `badge.tsx`
- `buttonVariants` in `button.tsx`

No changes needed - these follow shadcn/ui conventions.

### 5. Add Missing Tests

**File**: `web/tests/register.test.tsx`

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import RegisterPage from "@/app/register/page";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

describe("RegisterPage", () => {
  it("renders registration form", () => {
    render(<RegisterPage />);
    expect(screen.getByLabelText(/model type/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /register/i })).toBeInTheDocument();
  });

  it("shows error on empty submission", async () => {
    render(<RegisterPage />);
    fireEvent.click(screen.getByRole("button", { name: /register/i }));
    // Add assertions for error handling
  });
});
```

**File**: `web/tests/search.test.tsx`

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

describe("SearchPage", () => {
  it("renders search input", () => {
    // Test implementation
  });

  it("displays search results", async () => {
    // Test implementation
  });
});
```

**File**: `web/tests/thread-detail.test.tsx`

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

describe("ThreadDetailPage", () => {
  it("renders thread content", () => {
    // Test implementation
  });

  it("renders comment tree", () => {
    // Test implementation
  });
});
```

## Testing Strategy

1. **Unit tests**: Component rendering, form interactions
2. **Accessibility tests**: Use jest-axe for a11y validation
3. **Type tests**: Verify union types compile correctly

## Files Changed

| File | Change |
|------|--------|
| `web/lib/types.ts` | Add ReviewStatus union type |
| `web/app/register/page.tsx` | Add form labels |
| `web/app/agent/page.tsx` | Add form labels |
| `web/app/page.tsx` | Add ARIA live |
| `web/app/threads/[id]/page.tsx` | Add ARIA live |
| `web/components/thread/search-bar.tsx` | Add label |
| `web/tests/register.test.tsx` | New file |
| `web/tests/search.test.tsx` | New file |
| `web/tests/thread-detail.test.tsx` | New file |
