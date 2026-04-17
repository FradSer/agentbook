# Task 008b: Sandbox concurrency semaphore and hard-kill timeout — Green

**depends-on**: 008a

## Description

Implement a global `asyncio.Semaphore(8)` (or threading-equivalent for sync paths) guarding sandbox invocations. When the semaphore is full, return `sandbox_score=None` immediately, bump `sandbox_concurrency_rejection`, and fall back via the existing `SandboxUnavailable` path (cleanest integration with task 007b). For hard-kill, the docker provider gains a timeout watchdog that issues `docker kill --signal=KILL` and releases the semaphore in a `finally` block.

## Execution Context

**Task Number**: 008b of 41
**Phase**: Resilience — DoS gates
**Prerequisites**: Task 008a red tests committed.

## BDD Scenario

(Same scenarios as task 008a — see `bdd-specs.md`.)

## Files to Modify/Create

- Modify: `backend/application/service.py::AgentbookService.__init__` — add `self._sandbox_semaphore = asyncio.Semaphore(8)` (or the appropriate sync variant).
- Modify: `backend/application/service.py::improve_solution` sandbox branch — wrap sandbox calls with `try_acquire` semantics.
- Modify: `backend/infrastructure/sandbox/docker_sandbox.py` — watchdog + `docker kill --signal=KILL` on timeout.
- Modify: `backend/core/config.py` — add `sandbox_max_concurrent: int = 8` setting.

## Steps

### Step 1: Configure
- Add `sandbox_max_concurrent` setting (default 8, env var `SANDBOX_MAX_CONCURRENT`).

### Step 2: Semaphore
- In `AgentbookService.__init__`, create the semaphore sized to `settings.sandbox_max_concurrent`. Prefer a `threading.Semaphore` if `improve_solution` is sync; otherwise `asyncio.Semaphore`. Match the async-ness of the existing service code.
- Before each `self.sandbox.run(...)`, call `acquire(blocking=False)`. If it fails, bump `sandbox_concurrency_rejection`, raise `SandboxUnavailable()` (the existing task 007b path handles the fallback).

### Step 3: Hard-kill watchdog
- In `docker_sandbox.py::run`, spawn the container, then `await asyncio.wait_for(self._wait_container(cid), timeout=timeout_s)`. On `asyncio.TimeoutError`: `subprocess.run(["docker", "kill", "--signal=KILL", cid], check=False)`, wait max 5s for removal, raise `SandboxTimeout`.
- Always release the semaphore in a `finally` block — both on success and on `SandboxTimeout`.

### Step 4: Green
- Run 008a tests. Run integration test locally if docker available.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_sandbox_concurrency_timeout.py -v
RUN_DOCKER_TESTS=1 uv run pytest backend/tests/unit/test_sandbox_concurrency_timeout.py::test_timeout_hard_kills_container
uv run ruff check backend/application/service.py backend/infrastructure/sandbox/
```

## Success Criteria

- All 008a tests green.
- `sandbox_concurrency_rejection` counter increments on the 9th concurrent call.
- Docker integration test confirms no zombie container post-timeout.
