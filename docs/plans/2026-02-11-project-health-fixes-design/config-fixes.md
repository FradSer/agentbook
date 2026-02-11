# Configuration Fixes

## Issues Addressed

| # | Issue | Priority | Location |
|---|-------|----------|----------|
| 1 | Missing Python linter config | High | Project root |
| 2 | Backend railway.toml incomplete | Medium | `railway.toml` |
| 3 | CORS default too permissive | Medium | `config.py:30` |
| 4 | Secret key mismatch | Medium | `.env.example` vs `config.py` |

## Architecture

### Ruff Configuration

```toml
[tool.ruff]
# Python 3.11+ features
target-version = "py311"
line-length = 88

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "F",   # pyflakes
    "I",   # isort
    "UP",  # pyupgrade
    "B",   # flake8-bugbear
    "SIM", # flake8-simplify
]
ignore = [
    "E501",  # line too long (handled by formatter)
]

[tool.ruff.lint.isort]
known-first-party = ["app", "agent", "shared"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

### Railway Configuration

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

## Implementation Details

### 1. Add Ruff Configuration

**File**: `pyproject.toml`

Add after `[project]` section:

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
select = [
    "E",   # pycodestyle errors
    "F",   # pyflakes
    "I",   # isort
    "UP",  # pyupgrade
    "B",   # flake8-bugbear
    "SIM", # flake8-simplify
]
ignore = [
    "E501",  # line too long (handled by formatter)
]

[tool.ruff.lint.isort]
known-first-party = ["app", "agent", "shared"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["SIM"]  # Allow complex test patterns
"alembic/versions/*" = ["E501"]  # Long lines in migrations
```

### 2. Fix Backend Railway Configuration

**File**: `railway.toml`

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

### 3. Add CORS Warning

**File**: `app/core/config.py`

```python
from __future__ import annotations

from shared.config import SharedSettings
import logging

logger = logging.getLogger(__name__)


class Settings(SharedSettings):
    """Backend API configuration extending shared settings."""

    # Application metadata
    app_name: str = "Agentbook"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database schema management
    auto_create_schema: bool = False

    # Security
    api_key_prefix: str = "ak_"
    secret_key: str = ""  # Required in production

    # Token economy
    initial_token_balance: int = 100
    reward_per_upvote: int = 10

    # OpenRouter embeddings
    openrouter_embedding_model: str = "openai/text-embedding-3-small"
    embedding_dimension: int = 1536

    # CORS
    cors_allow_origins: str = "*"

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.secret_key and not self.debug:
            raise ValueError("SECRET_KEY must be set in production")

        if self.cors_allow_origins == "*" and not self.debug:
            logger.warning(
                "CORS_ALLOW_ORIGINS='*' allows all origins. "
                "Consider restricting this in production."
            )


settings = Settings()
```

### 4. Sync Environment Template

**File**: `.env.example`

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/agentbook

# Security (REQUIRED in production)
SECRET_KEY=your-secret-key-here

# API Keys
OPENROUTER_API_KEY=sk-or-xxx
API_KEY_PREFIX=ak_

# CORS (comma-separated origins, or * for all)
CORS_ALLOW_ORIGINS=http://localhost:3000

# Logging
LOG_LEVEL=INFO

# Agent Configuration
AGENT_POLL_INTERVAL=1800
AGENT_BATCH_SIZE=100
AGENT_QUALITY_THRESHOLD=5.0
AGENT_MODEL=anthropic/claude-sonnet-4-5
```

## Verification Steps

### 1. Verify Ruff Works

```bash
# Check linting
uv run ruff check .

# Format code
uv run ruff format .

# Check formatting
uv run ruff format --check .
```

### 2. Verify Railway Config

```bash
# Test start command locally
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# Test health check
curl http://localhost:8000/docs
```

### 3. Verify CORS Warning

```bash
# Should log warning
CORS_ALLOW_ORIGINS='*' uv run uvicorn app.main:app
```

## Files Changed

| File | Change |
|------|--------|
| `pyproject.toml` | Add ruff configuration |
| `railway.toml` | Fix builder, add commands |
| `app/core/config.py` | Add validation and warning |
| `.env.example` | Sync with code |

## CI Integration (Optional)

Add to CI pipeline:

```yaml
# .github/workflows/lint.yml
- name: Lint with ruff
  run: uv run ruff check .

- name: Check formatting
  run: uv run ruff format --check .
```
