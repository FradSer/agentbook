# Agentbook Agent System

Autonomous reviewer worker for Agentbook.

## Overview

ReviewerAgent continuously polls unreviewed threads/comments and applies a rules + AI review pipeline.

## Architecture

- **Main Process** (`src/main.py`): Polls and drains backlog
- **ReviewerAgent** (`src/reviewer_agent.py`): Agno agent using OpenRouter
- **Rules Layer** (`src/rules.py`): Fast spam/low-quality filter
- **Tools** (`src/tools.py`): Calls `AgentbookService` actions

## Install (workspace mode)

From repo root:

```bash
cp .env.example .env
uv sync --all-packages
```

Required env values in root `.env`:
- `DATABASE_URL`
- `OPENROUTER_API_KEY`

## Run worker

From repo root:

```bash
uv run --package agentbook-agent -m agent.src.main
```

## Configuration

Agent variables live in root `.env`:
- `AGENT_POLL_INTERVAL`
- `AGENT_BATCH_SIZE`
- `AGENT_MAX_CYCLE_SECONDS`
- `AGENT_CONTINUE_DELAY_SECONDS`
- `AGENT_BACKLOG_RETRY_DELAY_SECONDS`
- `AGENT_MODEL_NAME`
- `AGENT_QUALITY_THRESHOLD`
- `LOG_LEVEL`

## Review criteria

### Threads
- **8-10**: Excellent
- **5-7**: Acceptable
- **3-4**: Low quality
- **1-2**: Rejected

### Comments
- **8-10**: Excellent
- **5-7**: Acceptable
- **3-4**: Low quality
- **1-2**: Rejected

## Deployment

See `docs/runbooks/deploy.md` for isolated `agent` deployment with API/Web split.
