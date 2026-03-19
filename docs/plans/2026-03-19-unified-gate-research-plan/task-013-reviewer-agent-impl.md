# Task 013: Reviewer Agent — Implementation

**depends-on**: task-013-reviewer-agent-test, task-007-service-review-impl

## Description

Simplify `agent/src/reviewer_agent.py` to binary spam detection instructions. Update `agent/src/tools.py` to provide `approve_content` and `reject_content` tools that call the unified `update_review()` / `delete_content()` service methods. Update `agent/src/main.py` to process both problems and solutions in `review_content()`. Delete `agent/src/rules.py`.

## Execution Context

**Task Number**: 013b of 016
**Phase**: Agent Worker
**Prerequisites**: Task 013 tests written (Red). Task 007 (update_review/delete_content) must be complete for service methods to exist.

## BDD Scenario

```gherkin
Scenario: Reviewer agent processes both problems and solutions
  Given unreviewed problems and solutions exist
  When review_content is called
  Then all unreviewed problems are processed first
  Then all unreviewed solutions are processed
  And the total count of reviewed items is returned
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature` (Feature 1)

## Files to Modify/Create

- Modify: `agent/src/reviewer_agent.py`
- Modify: `agent/src/tools.py`
- Modify: `agent/src/main.py`
- Delete: `agent/src/rules.py`

## Steps

### Step 1: Update `agent/src/reviewer_agent.py`

Replace the `REVIEWER_INSTRUCTIONS` constant with the binary spam detection instructions from the architecture:
- The agent's only job is binary spam detection (APPROVE or REJECT)
- Low-quality but genuine content should be APPROVED
- The agent calls exactly one tool per content item: `approve_content` or `reject_content`

### Step 2: Update `agent/src/tools.py`

Replace `approve_thread`, `reject_thread`, `approve_comment`, `reject_comment` tools (if they exist as separate tools) with two unified tools:
- `approve_content(content_id: str, reason: str) -> str`: calls `service.update_review(UUID(content_id), "approved", 1.0, datetime.now(UTC))`
- `reject_content(content_id: str, reason: str) -> str`: calls `service.update_review(UUID(content_id), "rejected", 0.0, datetime.now(UTC))` then `service.delete_content(UUID(content_id))`

Both tools must handle exceptions and return error strings instead of raising.

### Step 3: Update `agent/src/main.py`

Replace the existing `review_threads()` / `review_comments()` (or equivalent) with a single `review_content(agent, service) -> int` function:
- Phase 1: fetch unreviewed problems via `service.get_unreviewed_problems(limit=batch_size, retry_error_before=...)`; for each, call `check_spam(description, "problem")`; auto-reject Stage 1 failures; send AI review prompt for passing ones
- Phase 2: fetch unreviewed solutions via `service.get_unreviewed_solutions(limit=batch_size, retry_error_before=...)`; for each, call `check_spam(content, "solution", {"steps": solution.steps})`; auto-reject Stage 1 failures; send AI review prompt for passing ones
- Return total count of processed items

### Step 4: Delete `agent/src/rules.py`

Remove the file. Any imports of `ContentRules` elsewhere in the agent must be removed.

### Step 5: Run tests (Green)

**Verification**: Run `uv run pytest agent/tests/test_reviewer_agent.py -v --tb=short` and verify all pass.

## Verification Commands

```bash
uv run pytest agent/tests/test_reviewer_agent.py -v --tb=short
uv run pytest agent/tests/ -q --tb=short
```

## Success Criteria

- All `test_reviewer_agent.py` tests pass
- `approve_content` and `reject_content` tools work for both problems and solutions
- `rules.py` deleted
- `review_content()` processes both content types in one pass
