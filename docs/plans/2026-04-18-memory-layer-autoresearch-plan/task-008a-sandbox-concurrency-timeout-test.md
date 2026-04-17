# Task 008a: Sandbox concurrency semaphore and hard-kill timeout — Red

**depends-on**: 007b

## Description

Red tests for two DoS gates: a global concurrency semaphore capping simultaneous sandbox runs at 8, and a hard-kill on timeout that leaves no orphan container. A 9th concurrent request receives `sandbox_score = None` immediately and falls back to Bayesian; a hanging run is killed via `docker kill --signal=KILL` with the concurrency slot released.

## Execution Context

**Task Number**: 008a of 41
**Phase**: Resilience — DoS gates
**Prerequisites**: Task 007b committed.

## BDD Scenario

```gherkin
Scenario: Global concurrency semaphore rejects the 9th concurrent run
  Given 8 sandbox runs are currently executing
  When a 9th run is requested via evaluate_improvement or verify
  Then the caller receives sandbox_score = None immediately
  And the decision falls back to Bayesian confidence
  And no 9th container is spawned
  And a sandbox_concurrency_rejection counter is incremented for /health

Scenario: Container hard-kill on timeout leaves no zombie
  Given a sandbox run hangs past SANDBOX_TIMEOUT_SECONDS = 30
  When the timeout fires
  Then the container is killed with docker kill --signal=KILL
  And no container remains in the sandbox_network ls after 5s
  And the concurrency semaphore is released
```

**Spec Source**: `../2026-04-18-memory-layer-autoresearch-design/bdd-specs.md`

## Files to Modify/Create

- Create: `backend/tests/unit/test_sandbox_concurrency_timeout.py`

## Steps

### Step 1: Fake blocking sandbox
- Create an async `BlockingSandbox` with a release event; its `run()` method awaits the event so callers can hold sandbox slots for the duration of the test.

### Step 2: Concurrency tests
- `test_concurrency_cap_rejects_ninth` — spin up 8 blocking runs; the 9th call to `service.improve_solution(...)` on a problem with `error_signature` must return immediately with `sandbox_score=None` and the decision must come from the Bayesian path. Assert `service.get_health_counter("sandbox_concurrency_rejection") == 1`.
- `test_concurrency_released_after_completion` — release one of the 8 blocked runs; assert a subsequent 9th call proceeds (gets a slot).

### Step 3: Timeout tests
- `test_timeout_hard_kills_container` — using the docker sandbox provider in an integration fixture (skipped unless `RUN_DOCKER_TESTS=1`), spawn a container that sleeps 60s; assert the timeout fires at 30s, `docker kill` is invoked, and `docker ps --filter network=sandbox_network` is empty within 5 seconds.
- `test_timeout_releases_semaphore` — unit-level: monkeypatch the sandbox to raise `SandboxTimeout`; assert that after the exception propagates, the concurrency semaphore's free-slot count returns to max.

### Step 4: Confirm Red
- All four tests fail because concurrency semaphore and hard-kill are not yet implemented.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_sandbox_concurrency_timeout.py -v
# + integration:
RUN_DOCKER_TESTS=1 uv run pytest backend/tests/unit/test_sandbox_concurrency_timeout.py::test_timeout_hard_kills_container
```

## Success Criteria

- Four failing tests.
- Docker integration test skipped cleanly in CI when `RUN_DOCKER_TESTS` unset.
