# Task 001: Foundation Setup

**depends-on**: (none)

## Description

Prepare the test infrastructure and settings for the unified platform. Remove V1 test fixtures from conftest.py, update the Settings class for outcome-based token rewards, and remove any unused imports that reference Thread, Comment, or Vote models.

## Execution Context

**Task Number**: 001 of 016
**Phase**: Setup
**Prerequisites**: None — this is the first task.

## BDD Scenario

```gherkin
Scenario: Test infrastructure forces in-memory repositories
  Given the test suite runs pytest
  When the autouse fixture is applied to any unit test
  Then the fixture sets database_url and openrouter_api_key to None
  And the AgentbookService is constructed with InMemoryProblemRepository
  And the AgentbookService is constructed with InMemorySolutionRepository
  And no Thread, Comment, or Vote repositories are referenced
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature` (implicit in all scenarios)

## Files to Modify/Create

- Modify: `tests/conftest.py`
- Modify: `app/core/config.py`

## Steps

### Step 1: Read existing conftest.py and config.py

Read `tests/conftest.py` to understand the existing fixture. Read `app/core/config.py` to understand the current Settings fields.

### Step 2: Update conftest autouse fixture (Red)

Write a test that verifies the autouse fixture no longer references `threads`, `comments`, or `votes` repositories. Confirm the test fails because the old fixture still passes those.

**Verification**: Run `uv run pytest tests/unit/ -k "test_fixture" --tb=short` and verify failure.

### Step 3: Update conftest.py (Green)

Remove `threads`, `comments`, and `votes` from the autouse fixture in `tests/conftest.py`. Update the fixture to only supply `agents`, `problems`, `solutions`, `outcomes`, `transactions`, `research_cycles` repositories to `AgentbookService`.

**Verification**: Run `uv run pytest tests/unit/ -k "test_fixture" --tb=short` and verify pass.

### Step 4: Update Settings

In `app/core/config.py`, rename `reward_per_upvote` to `reward_per_successful_outcome` (default value: 5). Ensure `initial_token_balance` remains 100.

### Step 5: Run existing unit tests

Run `uv run pytest tests/unit/ --tb=short` to see the current baseline of failures. Document which tests will need to be rewritten (all V1 tests referencing Thread/Comment/Vote).

## Verification Commands

```bash
uv run pytest tests/unit/ --tb=short
```

## Success Criteria

- conftest.py autouse fixture no longer references V1 repositories
- Settings has `reward_per_successful_outcome` instead of `reward_per_upvote`
- Unit test suite runs (failures are expected from V1 tests — they will be addressed in subsequent tasks)
