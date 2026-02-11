# Task 019: Write Frontend Page Tests

**Area**: Frontend
**Priority**: Medium
**BDD Scenario**: N/A (test coverage)

## Objective

Create tests for frontend pages that currently have no coverage.

## Files to Create

- `web/tests/register.test.tsx` (new)
- `web/tests/search.test.tsx` (new)
- `web/tests/thread-detail.test.tsx` (new)

## What to Implement

### Register Page Tests

```tsx
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

### Search Page Tests

```tsx
describe("SearchPage", () => {
  it("renders search input", () => {
    render(<SearchPage />);
    expect(screen.getByLabelText(/search/i)).toBeInTheDocument();
  });

  it("displays search results", async () => {
    // Mock API and test result rendering
  });
});
```

### Thread Detail Page Tests

```tsx
describe("ThreadDetailPage", () => {
  it("renders thread content", () => {
    // Mock thread data and test rendering
  });

  it("renders comment tree", () => {
    // Mock comments and test tree rendering
  });
});
```

## Verification

```bash
cd web && pnpm test register.test.tsx search.test.tsx thread-detail.test.tsx
```

Expected: Tests fail with missing mocks/implementation details.

## Dependencies

None - independent test files

## BDD References

None - test coverage improvement