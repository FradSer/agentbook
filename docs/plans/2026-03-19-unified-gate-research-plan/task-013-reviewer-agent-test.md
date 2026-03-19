# Task 013: Reviewer Agent — Test

**depends-on**: task-005-unified-gate-impl

## Description

Write unit tests for the simplified binary spam ReviewerAgent. Tests verify that the reviewer processes both problems and solutions in a single pass, that the `approve_content` and `reject_content` tools call the unified `update_review()` and `delete_content()` service methods, and that `ContentRules` / `agent/src/rules.py` is no longer used.

## Execution Context

**Task Number**: 013a of 016
**Phase**: Agent Worker
**Prerequisites**: Gate implemented (Task 005). Independent of API tasks (011, 012).

## BDD Scenario

```gherkin
Scenario: Reviewer processes both problems and solutions in one cycle
  Given 2 unreviewed problems and 3 unreviewed solutions
  When review_content is called
  Then the gate is applied to each problem and solution
  And the AI review prompt includes the content_id and description/content
  And 5 review prompts are sent to the AI agent

Scenario: approve_content tool calls update_review with status="approved"
  Given a content_id for a pending problem
  When approve_content(content_id, reason) is called
  Then service.update_review(content_id, status="approved", score=1.0) is called

Scenario: reject_content tool calls update_review and delete_content
  Given a content_id for a pending problem
  When reject_content(content_id, reason) is called
  Then service.update_review(content_id, status="rejected", score=0.0) is called
  And service.delete_content(content_id) is called

Scenario: Stage 1 gate rejection bypasses AI review
  Given a problem description "help" (too short)
  When review_content processes this problem
  Then check_spam is called and returns passed=False
  And the AI agent is NOT called for this problem
  And update_review with status="rejected" is called directly

Scenario: agent/src/rules.py is deleted or no longer imported
  Given the agent worker imports
  Then ContentRules cannot be imported from agent.src.rules
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature` (Feature 1 — Stage 2 AI check, retry on error)

## Files to Modify/Create

- Create: `agent/tests/test_reviewer_agent.py`

## Steps

### Step 1: Write tests (Red)

In `agent/tests/test_reviewer_agent.py`:
1. `get_reviewer_tools(service)` returns a list of 2 tools: `approve_content` and `reject_content`
2. Calling `approve_content(str(uuid), "reason")` calls `service.update_review(...)` with `status="approved"`
3. Calling `reject_content(str(uuid), "reason")` calls `service.update_review(...)` with `status="rejected"` AND `service.delete_content(...)`
4. `review_content(agent, service)` fetches unreviewed problems AND solutions
5. A problem that fails Stage 1 gate is rejected without calling the AI agent
6. `from agent.src.rules import ContentRules` raises `ImportError` (rules.py deleted)
7. The reviewer agent instructions include "binary spam detection" and "APPROVE" / "REJECT"

**Verification**: Run `uv run pytest agent/tests/test_reviewer_agent.py --tb=short` and verify failures.

## Verification Commands

```bash
uv run pytest agent/tests/test_reviewer_agent.py -v --tb=short
```

## Success Criteria

- All tests fail (Red phase complete)
- Tests confirm the unified review flow covers both problems and solutions
