# Task 007: Implement Agent Backoff

**Area**: Agent
**Priority**: Critical
**BDD Scenario**: All backoff scenarios

## Objective

Add exponential backoff to agent main loop error handling.

## Files to Modify

- `agent/src/main.py`

## What to Implement

### 1. Create BackoffState Dataclass

Add a dataclass to track backoff state:
- `retry_count: int = 0`
- `base_delay: float = 60.0`
- `max_delay: float = 3600.0`
- Methods: `get_delay()`, `increment()`, `reset()`

### 2. Update Main Loop

In the `main()` function:

1. Create `BackoffState` instance before the main loop
2. In the exception handler (around line 259):
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

- Task 006 (tests must exist first)
