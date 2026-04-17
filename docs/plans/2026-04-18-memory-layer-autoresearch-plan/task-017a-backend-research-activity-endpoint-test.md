# Task 017a: Backend /v1/research-activity endpoint — Red

**depends-on**: 007b

## Description

Red tests for `GET /v1/research-activity?memory_id=<uuid>&limit=&offset=`. Returns recent `ResearchCycle` rows joined with the verified outcomes that corroborate them. Public read. Rate-limited.

## Execution Context

**Task Number**: 017a of 41
**Phase**: Frontend enabler — API
**Prerequisites**: Task 007b (verified outcome pipeline exists).

## BDD Scenario

```gherkin
Scenario: /research timeline shows sandbox runs interleaved with research cycles
  Given a memory has 4 ResearchCycle rows
  And 2 of those cycles have an associated verified outcome
  When /research?memory_id=mem_42 renders
  Then all 4 cycles appear in reverse chronological order
  And the 2 sandbox-backed cycles expand to show stdout, stderr, exit_code
```

(The frontend view itself is tested in task 018; this task tests the backend endpoint only.)

**Spec Source**: `../2026-04-18-memory-layer-autoresearch-design/bdd-specs.md`

## Files to Modify/Create

- Create: `backend/tests/unit/test_api_research_activity.py`

## Steps

### Step 1: Tests
- `test_research_activity_returns_reverse_chronological` — seed 4 `ResearchCycle` + 2 verified outcomes; call endpoint; assert body is a list of 4 items ordered `created_at DESC`.
- `test_research_activity_includes_sandbox_details` — for the two cycles with a verified outcome, the response items include `stdout`, `stderr`, `exit_code` (sourced from `Outcome.notes` structured JSON, or a new SandboxResult derivation).
- `test_research_activity_unknown_memory_404` — unknown `memory_id`; assert 404.
- `test_research_activity_pagination` — `limit=2&offset=1`; assert the middle window is returned with proper `total`/`has_more` metadata.
- `test_research_activity_rate_limited` — 31 calls/minute triggers 429.

### Step 2: Confirm Red
- All five tests fail because the endpoint does not exist.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_api_research_activity.py -v
```

## Success Criteria

- Five failing tests.
- Pagination metadata shape agreed: `{"items": [...], "total": N, "has_more": bool}`.
