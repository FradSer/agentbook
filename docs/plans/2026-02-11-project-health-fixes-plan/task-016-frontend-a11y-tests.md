# Task 016: Write Frontend Form Labels Tests

**Area**: Frontend
**Priority**: Medium
**BDD Scenario**: Search input has label (ref: Scenario 1), API key input has label (ref: Scenario 2), Model type input has label (ref: Scenario 3)

## Objective

Create accessibility tests for form inputs with proper labels.

## Files to Create

- `web/tests/form-a11y.test.tsx` (new)

## What to Implement

Create test cases:

1. **Test search input has label**
   - Render `SearchBar` component
   - Assert input has associated label with `htmlFor` matching input `id`

2. **Test API key input has label**
   - Render `AgentPage` component
   - Assert API key input has associated label

3. **Test model type input has label**
   - Render `RegisterPage` component
   - Assert model type input has associated label

4. **Test labels are accessible to screen readers**
   - Use `getByLabelText` from testing-library
   - Assert all form inputs are findable via their labels

## Verification

```bash
cd web && pnpm test form-a11y.test.tsx
```

Expected: All tests **FAIL** (Red phase) - labels not yet added to components.

## Dependencies

None - independent test file

## BDD References

- Feature: Form inputs have accessible labels - Scenarios 1, 2, 3