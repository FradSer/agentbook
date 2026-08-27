"""Configuration validation tests.

Covers:
- Permissive CORS rejected in production (was warning, now hard-fail)
- Workers AI Gateway authentication and dimension validation
- Permissive CORS no warning in debug mode

The legacy ``secret_key`` validation was removed in 2026-05 — the field
had no consumers (no cookie / JWT / CSRF signing path) and the
production-validate check on it was decorative. If a future feature adds
a real signing context, re-introduce both the field and a corresponding
test.
"""

import logging

import pytest

from backend.core.config import Settings, validate_production_settings


class TestProductionCorsValidation:
    """Permissive CORS is hard-failed in production (was a warning)."""

    def test_app_rejects_wildcard_cors_in_production(self, monkeypatch):
        monkeypatch.setenv("CORS_ALLOW_ORIGINS", "*")
        monkeypatch.setenv("DEBUG", "false")

        settings = Settings()
        with pytest.raises(ValueError, match="CORS_ALLOW_ORIGINS"):
            validate_production_settings(settings)

    def test_app_accepts_explicit_origins_in_production(self, monkeypatch):
        monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://app.example.com")
        monkeypatch.setenv("DEBUG", "false")
        monkeypatch.setenv("AI_GATEWAY_BASE_URL", "https://gateway.example")
        monkeypatch.setenv("AI_GATEWAY_AUTH_TOKEN", "gateway-token")
        settings = Settings()
        settings.ai_gateway_base_url = "https://gateway.example"
        settings.ai_gateway_auth_token = "gateway-token"
        validate_production_settings(settings)
        assert "*" not in settings.cors_allow_origins

    def test_app_allows_wildcard_cors_in_debug_mode(self, monkeypatch):
        monkeypatch.setenv("CORS_ALLOW_ORIGINS", "*")
        monkeypatch.setenv("DEBUG", "true")

        settings = Settings()
        validate_production_settings(settings)


class TestEmbeddingDimensionValidation:
    """Workers AI Gateway embeddings require the 1024-dimensional column."""

    def test_gateway_embedding_dimension_must_match_active_column(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_DIMENSION", "768")
        monkeypatch.setenv("AI_GATEWAY_BASE_URL", "https://gateway.example")
        monkeypatch.setenv("AI_GATEWAY_AUTH_TOKEN", "gateway-token")
        monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://app.example.com")
        monkeypatch.setenv("DEBUG", "false")

        settings = Settings()
        settings.ai_gateway_base_url = "https://gateway.example"
        settings.ai_gateway_auth_token = "gateway-token"
        with pytest.raises(ValueError, match="EMBEDDING_DIMENSION"):
            validate_production_settings(settings)

    def test_gateway_with_valid_dimension_is_accepted_in_production(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_DIMENSION", "1024")
        monkeypatch.setenv("AI_GATEWAY_BASE_URL", "https://gateway.example")
        monkeypatch.setenv("AI_GATEWAY_AUTH_TOKEN", "gateway-token")
        monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://app.example.com")
        monkeypatch.setenv("DEBUG", "false")

        settings = Settings()
        settings.ai_gateway_base_url = "https://gateway.example"
        settings.ai_gateway_auth_token = "gateway-token"
        validate_production_settings(settings)


class TestCorsWarning:
    """Test CORS warning in different environments."""

    def test_permissive_cors_triggers_warning_in_production(self, monkeypatch, caplog):
        monkeypatch.setenv("CORS_ALLOW_ORIGINS", "*")
        monkeypatch.setenv("DEBUG", "false")

        with caplog.at_level(logging.WARNING):
            settings = Settings()
            assert settings.cors_allow_origins == "*"

        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("CORS_ALLOW_ORIGINS" in str(msg) for msg in warning_messages), (
            f"Expected CORS warning, but got: {warning_messages}"
        )

    def test_permissive_cors_no_warning_in_debug_mode(self, monkeypatch, caplog):
        monkeypatch.setenv("CORS_ALLOW_ORIGINS", "*")
        monkeypatch.setenv("DEBUG", "true")

        with caplog.at_level(logging.WARNING):
            settings = Settings()
            assert settings.cors_allow_origins == "*"

        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        cors_warnings = [
            msg for msg in warning_messages if "CORS_ALLOW_ORIGINS" in str(msg)
        ]
        assert len(cors_warnings) == 0, (
            f"Expected no CORS warning in debug mode, but got: {cors_warnings}"
        )
