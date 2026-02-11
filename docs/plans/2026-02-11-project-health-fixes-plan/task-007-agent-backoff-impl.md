# Task 007: Implement Agent Backoff

**Area**: Agent
**Priority**: Critical
**BDD Scenario**: All backoff scenarios (ref: Scenarios 1-4)

## Objective

Add exponential backoff to agent main loop error handling.

## Files to Modify

- `agent/src/backoff.py` (new)
- `agent/src/main.py`

## What to Implement

### 1. Create BackoffState Dataclass

Create `agent/src/backoff.py` with `BackoffState` dataclass:
- `retry_count: int = 0`
- `base_delay: float = 60.0`
- `max_delay: float = 3600.0`
- Methods: `get_delay()`, `increment()`, `reset()`

### 2. Update Main Loop

In the `main()` function:

1. Import and create `BackoffState` instance before the main loop
2. In the exception handler:
   - Call `backoff.increment()`
   - Get delay from `backoff.get_delay()`
   - Log error with retry count and delay
   - Sleep for the calculated delay
3. After successful cycle completion:
   - Call `backoff.reset()`

### 3. Use Settings for Base Delay

Use `settings.agent_poll_interval` as the base delay for backoff.

## Verification

```bash
uv run pytest agent/tests/test_backoff.py -v
```

Expected: All tests **PASS** (Green phase).

## Dependencies

**task-006-agent-backoff-tests.md** - Tests must exist first

## BDD References

- Feature: Agent recovers from errors with exponential backoff - Scenarios 1, 2, 3, 4