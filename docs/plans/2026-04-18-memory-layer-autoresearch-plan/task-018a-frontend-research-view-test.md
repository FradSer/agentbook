# Task 018a: Frontend /research view — Red

**depends-on**: 017b

## Description

Red tests for the `/research` page. Reads `/v1/research-activity?memory_id=<...>`. Renders the hill-climbing timeline. Sandbox-backed cycles expandable to show stdout/stderr/exit_code.

## Execution Context

**Task Number**: 018a of 41
**Phase**: Frontend reorg
**Prerequisites**: Task 017b committed.

## BDD Scenario

```gherkin
Scenario: /research timeline shows sandbox runs interleaved with research cycles
  Given a memory has 4 ResearchCycle rows
  And 2 of those cycles have an associated verified outcome
  When /research?memory_id=mem_42 renders
  Then all 4 cycles appear in reverse chronological order
  And the 2 sandbox-backed cycles expand to show stdout, stderr, exit_code
```

**Spec Source**: `../2026-04-18-memory-layer-autoresearch-design/bdd-specs.md`

## Files to Modify/Create

- Create: `frontend/tests/research-view.test.tsx`

## Steps

### Step 1: Tests
- Mock `fetch("/v1/research-activity?memory_id=mem_42")` with 4 items, 2 with `sandbox_run`.
- `test_research_page_renders_four_cycles_reverse_chronological` — render `<ResearchPage memoryId="mem_42" />`; assert 4 timeline entries; assert their order matches `created_at DESC`.
- `test_sandbox_entries_expandable_show_stdout_stderr_exit_code` — click expand on a sandbox-backed cycle; assert stdout/stderr/exit_code appear.
- `test_non_sandbox_entries_not_expandable` — cycles without `sandbox_run` show confidence delta but no expand button.
- `test_research_page_without_memory_id_shows_empty_state` — navigate to `/research` with no query; page renders empty-state copy telling the user to pick a memory.

### Step 2: Confirm Red
- All four tests fail.

## Verification Commands

```bash
cd frontend && pnpm test tests/research-view.test.tsx
```

## Success Criteria

- Four failing tests.
