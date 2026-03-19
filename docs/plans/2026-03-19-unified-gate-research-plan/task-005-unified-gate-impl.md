# Task 005: Unified Gate — Implementation

**depends-on**: task-005-unified-gate-test

## Description

Create `app/application/gate.py` as the single module for all content spam validation. Remove the old `app/application/quality_gate.py` (and `agent/src/rules.py` if not already handled in task-014). Update any imports that referenced the old quality gate.

## Execution Context

**Task Number**: 005b of 016
**Phase**: Application Layer — Gate
**Prerequisites**: Task 005 gate tests written (Red).

## BDD Scenario

```gherkin
Scenario: Problem passes basic rules and AI gate
  Given alice submits a problem with description "ModuleNotFoundError when running pytest in Docker Alpine container"
  When the content enters the gate
  Then Stage 1 basic rules pass
  And Stage 2 AI spam check returns "not spam"
  And the problem review_status is set to "approved"
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature` (Feature 1)

## Files to Modify/Create

- Create: `app/application/gate.py`
- Delete: `app/application/quality_gate.py`

## Steps

### Step 1: Create `app/application/gate.py`

Implement the `check_spam(content: str, content_type: str, metadata: dict | None = None) -> GateResult` function following the architecture specification:
- `GateResult` is a frozen dataclass with `passed: bool` and `reason: str | None = None`
- Constants: `MIN_PROBLEM_LENGTH = 20`, `MIN_SOLUTION_LENGTH = 10`
- Regex patterns: `_URL_ONLY`, `_SPAM_PHRASES` (buy cheap, click here, buy now), `_BUY_URL`
- Logic order: empty check → length check (type-specific) → character diversity → URL-only → spam phrases
- For solution content type: check `metadata.get("steps")` to allow short content if steps are provided

### Step 2: Remove imports of `quality_gate`

Search for all files that import from `app.application.quality_gate` and update them to import from `app.application.gate` instead. Key files to check:
- `app/application/service.py`

### Step 3: Delete `app/application/quality_gate.py`

Remove the file after confirming no remaining imports.

### Step 4: Run gate tests (Green)

**Verification**: Run `uv run pytest tests/unit/test_gate.py -v --tb=short` and verify all pass.

### Step 5: Run full unit tests

**Verification**: Run `uv run pytest tests/unit/ -q --tb=short` to confirm no regressions.

## Verification Commands

```bash
uv run pytest tests/unit/test_gate.py -v --tb=short
uv run pytest tests/unit/ -q --tb=short
```

## Success Criteria

- All `test_gate.py` tests pass
- `app/application/gate.py` created with `check_spam()` and `GateResult`
- `app/application/quality_gate.py` deleted
- No existing tests broken by the import change
