# Task 017: Implement Frontend Form Labels

**Area**: Frontend
**Priority**: Medium
**BDD Scenario**: Search input has label (ref: Scenario 1), API key input has label (ref: Scenario 2), Model type input has label (ref: Scenario 3)

## Objective

Add accessible labels to all form inputs.

## Files to Modify

- `web/app/register/page.tsx`
- `web/app/agent/page.tsx`
- `web/components/thread/search-bar.tsx`

## What to Implement

### Register Page (model-type input)

```tsx
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

### Agent Page (api-key input)

```tsx
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

### Search Bar (search-query input)

```tsx
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

Note: Import `Label` from `web/components/ui/label.tsx`.

## Verification

```bash
cd web && pnpm test form-a11y.test.tsx
```

Expected: All tests **PASS** (Green phase).

## Dependencies

**task-016-frontend-a11y-tests.md** - Tests must exist first

## BDD References

- Feature: Form inputs have accessible labels - Scenarios 1, 2, 3