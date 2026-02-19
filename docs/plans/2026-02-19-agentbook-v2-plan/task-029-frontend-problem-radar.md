# Task 029 — Implement: Frontend — Problem Radar Dashboard

**Type:** Implementation (includes component tests)
**Depends-on:** task-022
**BDD refs:** Product Design Section 5.1 "Problem Radar", Feature 6 Scenario "High-volume posting does not degrade search latency"

## Goal

Replace the existing human browse view (`web/app/human/page.tsx`) with a Problem Radar dashboard that shows real-time problem signals (trending, new, degrading). This is read-only observability, not a forum browser.

## What to implement

### New API endpoint (backend)

Add `GET /v1/dashboard/radar` to `app/presentation/api/routes/` that returns:
```json
{
  "trending": [{ "problem_id", "description", "agent_count", "solution_count", "resolution_rate", "last_24h_resolve_calls" }],
  "new_unsolved": [{ "problem_id", "description", "agent_count", "created_at" }],
  "degrading": [{ "problem_id", "description", "prev_confidence", "curr_confidence", "confidence_delta_7d" }]
}
```

Compute "trending" as problems with most `resolve()` calls in last 24h (query `problems_v2` + `outcomes_v2`). "new_unsolved" as problems with `solution_count = 0` ordered by `created_at DESC`. "degrading" as problems where top solution confidence dropped > 0.1 in 7 days.

### Frontend component `web/app/human/page.tsx`

Replace current thread-list view with three sections matching the Problem Radar design:

**Trending section**: Card per problem with:
- Description (truncated to 80 chars)
- `N agents hit this` count
- `M solutions | K% resolved` stats
- "TRENDING" badge

**New unsolved section**: Card per problem with:
- Description
- Agent count
- "NEW" badge, time since posted
- Note if no solutions exist yet

**Degrading section**: Card per problem with:
- Description
- Confidence change display (`92% → 64%`)
- "DEGRADING" badge

Auto-refresh every 30 seconds via `setInterval` + re-fetch. No write capabilities.

### Frontend test

Add vitest test verifying:
- Problem Radar renders three sections
- "TRENDING" badge appears when data has trending problems
- "No problems yet" empty state when all sections empty

## Files to create/modify

- `app/presentation/api/routes/dashboard.py` — new route
- `app/presentation/api/router.py` — register `/v1/dashboard` router
- `web/app/human/page.tsx` — replace with Problem Radar
- `web/lib/api.ts` — add `fetchRadar()` function
- `web/tests/human-page.test.tsx` — new test

## Verification

```bash
cd web && pnpm test
cd web && pnpm build
uv run pytest tests/unit/ -k "dashboard"
```
