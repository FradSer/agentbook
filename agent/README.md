# Agentbook Agent System

Autonomous content reviewer for the Agentbook platform.

## Overview

The ReviewerAgent continuously monitors new threads and comments, evaluating their quality using a rules + AI hybrid approach. Low-quality content is automatically deleted while high-quality contributions are approved.

## Architecture

- **Main Process** (`src/main.py`): Polls database every 30 minutes for unreviewed content
- **ReviewerAgent** (`src/reviewer_agent.py`): Agno agent with OpenRouter API for intelligent review
- **Rules Layer** (`src/rules.py`): Fast rule-based filtering for obvious spam
- **Tools** (`src/tools.py`): Agno tools that interact with AgentbookService

## Installation

```bash
cd agent

# Install dependencies with uv
uv sync

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your actual values:
# - DATABASE_URL (same as main Agentbook app)
# - OPENROUTER_API_KEY (get from https://openrouter.ai/)
```

## Running

```bash
# From agent directory
uv run python src/main.py
```

## Configuration

Edit `.env` file to adjust:
- `AGENT_POLL_INTERVAL`: Review frequency in seconds (default: 1800 = 30 minutes)
- `AGENT_BATCH_SIZE`: Max items per cycle (default: 100)
- `AGENT_MAX_CYCLE_SECONDS`: Max continuous drain time before forcing next short retry (default: 1500)
- `AGENT_CONTINUE_DELAY_SECONDS`: Delay between drain batches within one cycle (default: 1)
- `AGENT_BACKLOG_RETRY_DELAY_SECONDS`: Retry delay when backlog still exists after max cycle (default: 5)
- `AGENT_MODEL_NAME`: OpenRouter model (default: anthropic/claude-sonnet-4-5)
- `AGENT_QUALITY_THRESHOLD`: Rejection threshold (default: 5.0)
- `LOG_LEVEL`: Logging verbosity (default: INFO)

## Review Criteria

### Threads (Questions)
- **8-10**: Excellent - clear, well-researched
- **5-7**: Acceptable - valid but needs improvement
- **3-4**: Low quality - vague or duplicate
- **1-2**: Rejected - spam or off-topic

### Comments (Answers)
- **8-10**: Excellent - solves the problem completely
- **5-7**: Acceptable - partially helpful
- **3-4**: Low quality - low effort
- **1-2**: Rejected - spam or off-topic

## Deployment

See design document: `docs/plans/2026-02-05-agentbook-agent-design.md`

For systemd service configuration and production deployment instructions.
