"""
Shared configuration between Backend API and ReviewerAgent.

This module defines the base configuration class that is inherited by both
the FastAPI backend (backend.core.config.Settings) and the ReviewerAgent
(agent.src.config.AgentSettings).
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class SharedSettings(BaseSettings):
    """
    Shared configuration between Backend API and ReviewerAgent.

    Both systems connect to the same PostgreSQL database and may use
    the same OpenRouter API key for different purposes (backend for
    embeddings, agent for AI review).

    Each service has its own .env file generated from the root .env
    by scripts/sync-env.sh. Subclasses override env_file to point
    to their service-specific .env.

    Attributes:
        database_url: PostgreSQL connection string. If None, backend falls
            back to in-memory repositories for development.
        openrouter_api_key: API key for OpenRouter services. If None,
            embedding search is disabled in backend.
    """

    # Database configuration
    database_url: str | None = None

    # OpenRouter API configuration
    openrouter_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )
