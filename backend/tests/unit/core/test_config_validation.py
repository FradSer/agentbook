"""Configuration validation tests.

Covers:
- Permissive CORS rejected in production (was warning, now hard-fail)
- Voyage + EMBEDDING_VERSION=v1 rejected in production (dim mismatch)
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

        settings = Settings()
        validate_production_settings(settings)
        assert "*" not in settings.cors_allow_origins

    def test_app_allows_wildcard_cors_in_debug_mode(self, monkeypatch):
        monkeypatch.setenv("CORS_ALLOW_ORIGINS", "*")
        monkeypatch.setenv("DEBUG", "true")

        settings = Settings()
        validate_production_settings(settings)


class TestEmbeddingDimensionValidation:
    """Voyage outputs 1024-dim vectors; the legacy ``problems.embedding``
    column is ``vector(1536)``. With ``EMBEDDING_VERSION=v1`` writes
    target the legacy column and pgvector rejects the dim mismatch on
    commit. We hard-fail at boot in this exact configuration."""

    def test_voyage_with_v1_column_is_rejected_in_production(self, monkeypatch):
        monkeypatch.setenv("VOYAGE_API_KEY", "vk-test")
        monkeypatch.setenv("EMBEDDING_VERSION", "v1")
        monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://app.example.com")
        monkeypatch.setenv("DEBUG", "false")

        settings = Settings()
        with pytest.raises(ValueError, match="EMBEDDING_VERSION"):
            validate_production_settings(settings)

    def test_voyage_with_v2_column_is_accepted_in_production(self, monkeypatch):
        monkeypatch.setenv("VOYAGE_API_KEY", "vk-test")
        monkeypatch.setenv("EMBEDDING_VERSION", "v2")
        monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://app.example.com")
        monkeypatch.setenv("DEBUG", "false")

        settings = Settings()
        validate_production_settings(settings)

    def test_no_voyage_key_passes_either_version(self, monkeypatch):
        # Without a Voyage key the OpenRouter / Fallback chain runs at
        # whatever dim the active column expects. The startup check
        # only fires for the specific Voyage+v1 mismatch.
        monkeypatch.setenv("EMBEDDING_VERSION", "v1")
        monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://app.example.com")
        monkeypatch.setenv("DEBUG", "false")

        settings = Settings()
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
