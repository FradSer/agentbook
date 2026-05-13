# Task 001: Land BDD feature file with all 27 scenarios

**depends-on**: (none)

## Description

Land `backend/tests/features/live_research_banner.feature` containing the full Gherkin spec from the design folder verbatim. This task is per CLAUDE.md's BDD-driven TDD constraint: the feature file lands first, before any production code or test infrastructure that asserts against it. This file becomes the canonical contract every later task references.

## Execution Context

**Task Number**: 001 of 20
**Phase**: Foundation — BDD contract
**Prerequisites**: None

## BDD Scenario

This task carries the full spec, not a single scenario. The 27 scenarios are listed individually in the plan's BDD Coverage table and are reproduced verbatim in `bdd-specs.md`. Below is the file's required header so the executor knows what to copy:

```gherkin
@frontend @backend @sse
Feature: Live Research Banner

  As a human visitor on the homepage
  I want a banner that names the problem the ReviewerAgent is currently
  hill-climbing
  So that I can see the agentbook is alive and follow active work in real time

  Background:
    Given the homepage is mounted
    And the public dashboard endpoints are reachable without an API key
    And the freshness window for research_started_at is 360 seconds
    And the SSE endpoint is "/v1/dashboard/research/stream"
    And the REST snapshot endpoint is "/v1/dashboard/research/live"

  # ... 27 scenarios (full text in design's bdd-specs.md) ...
```

**Spec Source**: `../2026-05-01-live-research-banner-design/bdd-specs.md` (lines 33-313 — the Gherkin block between the triple-backtick fences)

## Files to Modify/Create

- Create: `backend/tests/features/live_research_banner.feature`

## Steps

### Step 1: Copy Gherkin verbatim
- Open `docs/plans/2026-05-01-live-research-banner-design/bdd-specs.md`.
- Extract every line inside the triple-backtick `gherkin` fence.
- Write to `backend/tests/features/live_research_banner.feature` byte-for-byte.

### Step 2: Verify `Scenario:` count
- Run `grep -c "^  Scenario:" backend/tests/features/live_research_banner.feature`. Expected output: `27`.

### Step 3: Confirm no behaviour-binding step definitions exist yet
- Step definitions are added scenario-by-scenario in later tasks. This task lands the feature file only. Do NOT create `.py` step bindings here.

## Verification Commands

```bash
test -f backend/tests/features/live_research_banner.feature
grep -c "^  Scenario:" backend/tests/features/live_research_banner.feature   # → 27
grep -c "^@" backend/tests/features/live_research_banner.feature              # → ≥ 1 (Feature-level tags)
```

## Success Criteria

- File exists at the exact path above.
- Exactly 27 `Scenario:` lines.
- File starts with the `Feature: Live Research Banner` header and ends after the final scenario line.
- No step definition `.py` files are created in this task.
