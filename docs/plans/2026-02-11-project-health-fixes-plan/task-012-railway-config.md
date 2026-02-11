# Task 012: Fix Railway Configuration

**Area**: Configuration
**Priority**: Medium
**BDD Scenario**: N/A (deployment config)

## Objective

Update backend railway.toml with complete deployment settings.

## Files to Modify

- `railway.toml`

## What to Implement

### Update Railway Configuration

Replace current content with:

```toml
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/docs"
healthcheckTimeout = 120
preDeployCommand = "uv run alembic upgrade head"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

Key changes:
- Change builder from `RAILPACK` to `NIXPACKS`
- Add `startCommand` for running the server
- Add `healthcheckPath` pointing to `/docs`
- Add `restartPolicyType` and `restartPolicyMaxRetries`

## Verification

```bash
# Verify syntax is valid TOML
python -c "import tomllib; tomllib.load(open('railway.toml', 'rb'))"
```

Expected: No errors.

## Dependencies

- Task 011 (ruff config done)
