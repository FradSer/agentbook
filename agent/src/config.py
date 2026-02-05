import os
from pathlib import Path

# Paths
AGENT_ROOT = Path(__file__).parent.parent
DATA_DIR = AGENT_ROOT / "data"
STATE_DB = DATA_DIR / "agent_state.db"

# Polling
POLL_INTERVAL = 30 * 60  # 30 minutes in seconds
BATCH_SIZE = 100  # Max items per poll

# OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = "anthropic/claude-sonnet-4-5"

# Database (reuse Agentbook's PostgreSQL)
DATABASE_URL = os.getenv("DATABASE_URL")

# Thresholds
QUALITY_THRESHOLD = 5.0  # Score below this = reject
