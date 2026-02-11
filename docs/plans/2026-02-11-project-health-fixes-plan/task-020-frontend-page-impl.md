# Task 020: Implement Frontend Page Tests

**Area**: Frontend
**Priority**: Medium
**BDD Scenario**: N/A (test coverage)

## Objective

Implement proper test setup and mocks for frontend page tests.

## Files to Modify

- `web/tests/register.test.tsx`
- `web/tests/search.test.tsx`
- `web/tests/thread-detail.test.tsx`

## What to Implement

### Add Test Mocks and Implement Tests

For each test file:

1. Mock `next/navigation` router:
```tsx
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));
```

2. Mock API client functions as needed

3. Complete test implementations with proper assertions

### Register Page

- Verify form renders with all fields
- Test validation shows errors for empty submission
- Test successful submission redirects

### Search Page

- Verify search input renders
- Test search query updates
- Mock API and test result display

### Thread Detail Page

- Mock thread data
- Test thread content rendering
- Test comment tree structure
- Test loading states

## Verification

```bash
cd web && pnpm test register.test.tsx search.test.tsx thread-detail.test.tsx
```

Expected: All tests **PASS** (Green phase).

## Dependencies

**task-019-frontend-page-tests.md** - Test files must exist first

## BDD References

None - test coverage improvement