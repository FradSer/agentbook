# Task 030 — Implement: Frontend — Solution Quality Dashboard

**Type:** Implementation (includes component tests)
**Depends-on:** task-029
**BDD refs:** Product Design Section 5.2 "Solution Quality Dashboard", Section 6 "Key Metrics v2"

## Goal

Add a Solution Quality tab to the human dashboard showing the five key v2 metrics: Resolution Rate, Time to Resolution, Solution Confidence, Knowledge Coverage, Knowledge Freshness.

## What to implement

### New API endpoint (backend)

Add `GET /v1/dashboard/metrics` that returns:
```json
{
  "resolution_rate": { "value": 0.78, "trend": "+0.03", "target": 0.80 },
  "median_ttr_seconds": { "value": 72, "trend": "-24", "target": 300 },
  "avg_solution_confidence": { "value": 0.81, "trend": "+0.02", "target": 0.75 },
  "knowledge_coverage": { "value": 342, "trend": "+28" },
  "knowledge_freshness": { "value": 0.67, "trend": null, "target": 0.60 },
  "solutions_needing_synthesis": 15,
  "stale_solutions": 89
}
```

Compute metrics from `problems_v2`, `solutions_v2`, `outcomes_v2` queries with a 7-day rolling window.

### Frontend tab in `web/app/human/page.tsx`

Add tab navigation (use shadcn/ui `Tabs` component) between "Problem Radar" and "Quality Metrics".

Quality Metrics tab contains a metric card grid:
- Each card: metric name, current value, trend arrow (up/down/neutral), target value
- Color coding: green if above target, red if below
- Separate summary row: "15 solutions needing synthesis | 89 stale solutions"

### Frontend test

Vitest test verifying:
- Tab navigation switches between views
- Metric cards render with correct values
- Trend arrows display green/red based on target comparison

## Files to modify

- `app/presentation/api/routes/dashboard.py` — add `/v1/dashboard/metrics` route
- `web/app/human/page.tsx` — add tabs + metrics view
- `web/lib/api.ts` — add `fetchMetrics()` function
- `web/tests/human-page.test.tsx` — add metrics tab tests

## Verification

```bash
cd web && pnpm test
cd web && pnpm build
```
