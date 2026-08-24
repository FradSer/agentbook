---
name: verify
description: Run the unit test suite with `make fast`. Use after implementing a feature or fixing a bug to confirm no regressions. Does not require Docker or a live database.
disable-model-invocation: true
---

Run the unit test suite:

```bash
make fast
```

This runs `uv run pytest` with only unit tests (no `@pytest.mark.smoke` or `@pytest.mark.perf`). All tests use in-memory repositories — no Docker or PostgreSQL needed.

If any test fails, read the full output, identify the root cause, and fix it before marking work done.

To run a single test:
```bash
uv run pytest tests/path/to/test.py::test_function_name
```

To run the full suite including integration and web:
```bash
make full
```
