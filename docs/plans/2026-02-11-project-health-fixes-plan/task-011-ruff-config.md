# Task 011: Add Ruff Configuration

**Area**: Configuration
**Priority**: High
**BDD Scenario**: Unused imports are detected, Code is formatted

## Objective

Add ruff linter configuration to pyproject.toml.

## Files to Modify

- `pyproject.toml`

## What to Implement

### Add Ruff Configuration Section

Add the following to `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py311"
line-length = 88
exclude = [
    ".git",
    ".venv",
    "__pycache__",
    "*.egg-info",
    ".mypy_cache",
    ".pytest_cache",
    "agent/.venv",
]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
ignore = ["E501"]

[tool.ruff.lint.isort]
known-first-party = ["app", "agent", "shared"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

### Run Initial Format

After adding config:
1. Run `uv run ruff format .`
2. Run `uv run ruff check . --fix`

## Verification

```bash
uv run ruff check .
uv run ruff format --check .
```

Expected: No errors reported.

## Dependencies

- Task 010 (agent tests done)
