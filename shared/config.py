"""
Shared configuration between Backend API and ReviewerAgent.

This module defines the base configuration class that is inherited by both
the FastAPI backend (backend.core.config.Settings) and the ReviewerAgent
(agent.src.config.AgentSettings).

Both Python services read from the single root ``.env`` file. Frontend
env is synced separately via ``scripts/sync-env.sh``.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROOT_ENV = str(PROJECT_ROOT / ".env")


class SharedSettings(BaseSettings):
    """Shared configuration between Backend API and ReviewerAgent.

    All Python services read the root ``.env`` directly (single source of
    truth). ``extra="ignore"`` lets each subclass silently skip variables
    it does not declare.
    """

    # Database configuration
    database_url: str | None = None

    # OpenRouter API configuration
    openrouter_api_key: str | None = None

    # Voyage AI (commercial embedding + reranking). When set, Voyage takes
    # precedence over OpenRouter in the resolver chain. Used by both the
    # backend API search path and the Reviewer agent so the two pipelines
    # stay symmetric.
    voyage_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=ROOT_ENV,
        env_file_encoding="utf-8",
        extra="ignore",
    )
