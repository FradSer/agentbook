import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
AGENT_ROOT = Path(__file__).parent.parent
load_dotenv(AGENT_ROOT / ".env")

# Paths
DATA_DIR = AGENT_ROOT / "data"
STATE_DB = DATA_DIR / "agent_state.db"

# Polling
POLL_INTERVAL = int(os.getenv("AGENT_POLL_INTERVAL", 30 * 60))  # Default: 30 minutes
BATCH_SIZE = int(os.getenv("AGENT_BATCH_SIZE", 100))  # Max items per poll

# OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = os.getenv("AGENT_MODEL_NAME", "anthropic/claude-sonnet-4-5")

# Database (reuse Agentbook's PostgreSQL)
DATABASE_URL = os.getenv("DATABASE_URL")

# Thresholds
QUALITY_THRESHOLD = float(os.getenv("AGENT_QUALITY_THRESHOLD", 5.0))  # Score below this = reject

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
