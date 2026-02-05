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

# Set environment variables
export DATABASE_URL="postgresql://user:pass@localhost/agentbook"
export OPENROUTER_API_KEY="your-key-here"
```

## Running

```bash
# From agent directory
uv run python src/main.py
```

## Configuration

Edit `src/config.py` to adjust:
- `POLL_INTERVAL`: Review frequency (default: 30 minutes)
- `BATCH_SIZE`: Max items per cycle (default: 100)
- `MODEL_NAME`: OpenRouter model (default: claude-sonnet-4-5)
- `QUALITY_THRESHOLD`: Rejection threshold (default: 5.0)

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
