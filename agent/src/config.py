"""
ReviewerAgent configuration extending shared settings.

This module defines agent-specific configuration while inheriting shared
settings (database_url, openrouter_api_key) from the shared.config module.
"""

from __future__ import annotations

from pathlib import Path

from shared.config import SharedSettings

AGENT_ROOT = Path(__file__).resolve().parent.parent


class AgentSettings(SharedSettings):
    """ReviewerAgent configuration extending shared settings."""

    # Polling configuration
    agent_poll_interval: int = 1800  # 30 minutes in seconds
    agent_batch_size: int = 100  # Max items per poll
    agent_max_cycle_seconds: int = 1500  # 25 minutes
    agent_continue_delay_seconds: float = 1.0
    agent_backlog_retry_delay_seconds: int = 5

    # Agent-specific OpenRouter configuration
    agent_model_name: str = "anthropic/claude-sonnet-4-5"

    # Research loop configuration
    agent_research_enabled: bool = True
    agent_research_batch_size: int = 5
    agent_research_min_confidence_threshold: float = 0.7
    agent_research_cooldown_hours: int = 6
    agent_research_per_candidate_timeout_seconds: int = 300  # 5 min per candidate (autoresearch: 10 min)
    agent_researcher_instructions_path: str = ""  # override path for program.md

    # Logging
    log_level: str = "INFO"


# Singleton instance
settings = AgentSettings()
