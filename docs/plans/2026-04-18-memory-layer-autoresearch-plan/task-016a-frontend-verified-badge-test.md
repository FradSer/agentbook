# Task 016a: Frontend verified badge and dual score — Red

**depends-on**: 015b, 002b

## Description

Red tests for the verified badge rendered on `/memories` list and `/memories/[id]` detail when a memory has at least one `Outcome(kind="verified")`, plus the dual-score panel on the detail page showing global `best_confidence` and the best per-environment score. Legacy outcomes with `kind IS NULL` do NOT trigger the badge.

## Execution Context

**Task Number**: 016a of 41
**Phase**: Frontend reorg
**Prerequisites**: Tasks 015b (route) and 002b (API returns `kind`).

## BDD Scenario

```gherkin
Scenario: /memories shows verified badge when any solution has verified outcomes
  Given a memory has at least one Outcome(kind="verified")
  When the memories list page renders
  Then a coral "Verified" pill is shown in that memory's row
  And the pill is accessible via aria-label="sandbox verified"

Scenario: /memories shows dual score on detail page
  Given a memory with global best_confidence 0.71
  And per-environment score 0.82 for os=ubuntu-22
  When the detail page renders
  Then both scores are visible
  And the per-environment score is labelled with the environment key

Scenario: Verified badge ignores legacy sandbox outcomes missing the kind field
  Given a historical outcome with reporter_id=SANDBOX_AGENT_ID and kind IS NULL
  And the backfill migration has not yet run
  When the memory detail page renders
  Then the verified badge is NOT shown
  And once the backfill runs, the badge appears on the next request
```

**Spec Source**: `../2026-04-18-memory-layer-autoresearch-design/bdd-specs.md`

## Files to Modify/Create

- Create: `frontend/tests/memories-verified-badge.test.tsx`

## Steps

### Step 1: Component tests
- Using React Testing Library + vitest, render the `<MemoriesList>` and `<MemoryDetail>` components with fixture memory data.
- `test_list_shows_verified_pill_when_kind_verified` — fixture has one outcome with `kind="verified"`; assert `getByLabelText("sandbox verified")` is present and has a coral class applied.
- `test_list_omits_verified_pill_when_only_observed` — fixture has only observed outcomes; assert the badge is absent.
- `test_list_omits_verified_pill_when_kind_missing` — fixture has outcome with `reporter_id == SANDBOX_AGENT_ID` but `kind` absent from response; badge NOT shown.
- `test_detail_shows_dual_score` — fixture with `best_confidence=0.71` and environment scores `{"os_ubuntu-22": 0.82}`; detail renders both "0.71" and "0.82" with environment label.

### Step 2: Confirm Red
- All four tests fail.

## Verification Commands

```bash
cd frontend && pnpm test tests/memories-verified-badge.test.tsx
```

## Success Criteria

- Four failing tests referencing components that do not yet exist.
