# Task 005: Unified Gate — Test

**depends-on**: task-002-domain-models-impl

## Description

Write unit tests for the new unified gate module `app/application/gate.py`. Tests cover all Stage 1 basic rule scenarios from Feature 1 of the BDD specs: minimum length, URL-only detection, spam phrase patterns, character diversity check, and the different behavior for `problem` vs `solution` content types.

## Execution Context

**Task Number**: 005a of 016
**Phase**: Application Layer — Gate
**Prerequisites**: Task 002 complete (domain models exist). This task is independent of Tasks 003 and 004.

## BDD Scenario

```gherkin
Scenario: Problem passes basic rules
  Given a problem description "ModuleNotFoundError when running pytest in Docker Alpine container"
  When check_spam is called with content_type="problem"
  Then GateResult.passed is True
  And GateResult.reason is None

Scenario: Problem rejected — too short
  Given a problem description "help"
  When check_spam is called with content_type="problem"
  Then GateResult.passed is False
  And GateResult.reason is "Problem description too short (minimum 20 characters)"

Scenario: Problem rejected — spam pattern detected
  Given a problem description "buy cheap hosting at http://spam.example.com"
  When check_spam is called with content_type="problem"
  Then GateResult.passed is False
  And GateResult.reason is "spam_detected"

Scenario: Problem rejected — URL only
  Given a problem description "https://example.com/some-link"
  When check_spam is called with content_type="problem"
  Then GateResult.passed is False
  And GateResult.reason is "spam_detected"

Scenario: Problem rejected — low character diversity
  Given a problem description "aaaaaaaaaaaaaaaaaaaaa"
  When check_spam is called with content_type="problem"
  Then GateResult.passed is False
  And GateResult.reason is "quality_check_failed"

Scenario: Solution rejected — too short without steps
  Given a solution content "use pip" and no steps
  When check_spam is called with content_type="solution"
  Then GateResult.passed is False
  And GateResult.reason is "Solution too short"

Scenario: Solution with short content but valid steps passes Stage 1
  Given a solution content "Fix it:" and steps ["pip install package", "restart container"]
  When check_spam is called with content_type="solution" and metadata={"steps": [...]}
  Then GateResult.passed is True

Scenario: Solution rejected by spam pattern
  Given a solution content "buy cheap licenses at http://deals.example.com"
  When check_spam is called with content_type="solution"
  Then GateResult.passed is False
  And GateResult.reason is "spam_detected"
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature` (Feature 1 — Stage 1 scenarios)

## Files to Modify/Create

- Create: `tests/unit/test_gate.py`

## Steps

### Step 1: Write tests (Red)

In `tests/unit/test_gate.py`, import `check_spam` and `GateResult` from `app.application.gate` and write tests for each scenario above, plus:
- Empty content returns `passed=False` with `reason="Empty content"`
- Whitespace-only content returns `passed=False`
- `GateResult` is a frozen dataclass with `passed: bool` and `reason: str | None`
- The `"click here"` phrase is detected as spam
- The `"buy now"` phrase is detected as spam
- Content with `\bbuy\b.+https?://` pattern is detected as spam

**Verification**: Run `uv run pytest tests/unit/test_gate.py --tb=short` and verify `ModuleNotFoundError` or `ImportError` (gate.py does not exist yet).

## Verification Commands

```bash
uv run pytest tests/unit/test_gate.py -v --tb=short
```

## Success Criteria

- All `test_gate.py` tests fail with ImportError or assertion failures (Red phase complete)
- Test file covers all Feature 1 Stage 1 scenarios
