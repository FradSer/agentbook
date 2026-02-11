# Task 006: Write Agent Backoff Tests

**Area**: Agent
**Priority**: Critical
**BDD Scenario**: First error uses base delay, Second error doubles delay, Delay caps at maximum, Success resets backoff

## Objective

Create tests for the exponential backoff mechanism in agent error recovery.

## Files to Create

- `agent/tests/__init__.py` (new)
- `agent/tests/test_backoff.py` (new)

## What to Implement

Create test cases for `BackoffState` class:

1. **Test initial state**
   - Create new `BackoffState()`
   - Assert `retry_count == 0`
   - Assert `get_delay() == base_delay` (default 60s)

2. **Test exponential growth**
   - Create `BackoffState(base_delay=60.0)`
   - Call `increment()`, assert `get_delay() == 120.0`
   - Call `increment()` again, assert `get_delay() == 240.0`

3. **Test max delay cap**
   - Create `BackoffState(base_delay=60.0, max_delay=300.0)`
   - Call `increment()` 10 times
   - Assert `get_delay() == 300.0` (capped at max)

4. **Test reset on success**
   - Create `BackoffState()`, increment multiple times
   - Call `reset()`
   - Assert `retry_count == 0`
   - Assert `get_delay() == base_delay`

## Verification

```bash
uv run pytest agent/tests/test_backoff.py -v
```

Expected: All tests **FAIL** (Red phase) - BackoffState not implemented yet.

## Dependencies

- Task 005 (backend changes done)
