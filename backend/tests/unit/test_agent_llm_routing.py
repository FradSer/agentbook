"""Tests for agent LLM provider routing."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from agent.src import llm


@pytest.fixture(autouse=True)
def _no_gemini_key_by_default(monkeypatch):
    """Neutralize a real GEMINI_API_KEY loaded from .env.

    Gemini is first in the ``auto`` precedence, so without this the
    NVIDIA/CF/OpenRouter routing assertions below would all resolve to gemini.
    Tests that exercise Gemini routing set the key explicitly.
    """
    monkeypatch.setattr(llm.settings, "gemini_api_key", None)
    llm._ROTATORS.clear()


def test_resolve_model_id_falls_back_from_minimax_on_cf_gateway(monkeypatch):
    monkeypatch.setattr(llm.settings, "agent_llm_provider", "cf_aig")
    monkeypatch.setattr(
        llm.settings,
        "cf_aig_url",
        "https://gateway.example/compat",
    )
    monkeypatch.setattr(llm.settings, "cf_aig_token", "token")
    monkeypatch.setattr(
        llm.settings,
        "agent_model_name",
        "google-ai-studio/gemini-3.1-flash-lite-preview",
    )
    monkeypatch.setattr(
        llm.settings, "agent_researcher_model_name", "minimax/minimax-m2.5"
    )

    assert llm.resolve_model_id(researcher=True) == (
        "google-ai-studio/gemini-3.1-flash-lite-preview"
    )


def test_resolve_model_id_keeps_researcher_when_cf_not_configured(monkeypatch):
    monkeypatch.setattr(llm.settings, "cf_aig_url", "")
    monkeypatch.setattr(llm.settings, "cf_aig_token", "")
    monkeypatch.setattr(
        llm.settings, "agent_researcher_model_name", "minimax/minimax-m2.5"
    )

    assert llm.resolve_model_id(researcher=True) == "minimax/minimax-m2.5"


def test_auto_prefers_nvidia_when_nvidia_api_key_set(monkeypatch):
    monkeypatch.setattr(llm.settings, "agent_llm_provider", "auto")
    monkeypatch.setattr(llm.settings, "nvidia_api_key", "nvapi-test")
    monkeypatch.setattr(llm.settings, "cf_aig_url", "https://gateway.example")
    monkeypatch.setattr(llm.settings, "cf_aig_token", "token")

    assert llm.active_llm_provider() == "nvidia"


def test_build_agent_model_uses_nvidia_openai_compatible_endpoint(monkeypatch):
    monkeypatch.setattr(llm.settings, "agent_llm_provider", "nvidia")
    monkeypatch.setattr(llm.settings, "nvidia_api_key", "nvapi-test")
    monkeypatch.setattr(
        llm.settings,
        "nvidia_base_url",
        "https://integrate.api.nvidia.com/v1",
    )
    monkeypatch.setattr(
        llm.settings,
        "agent_researcher_model_name",
        "deepseek-ai/deepseek-v4-pro",
    )

    with patch("agent.src.llm.OpenAILike") as mock_like:
        llm.build_agent_model(researcher=True)

    mock_like.assert_called_once()
    kwargs = mock_like.call_args.kwargs
    assert kwargs["id"] == "deepseek-ai/deepseek-v4-pro"
    assert kwargs["api_key"] == "nvapi-test"
    assert kwargs["base_url"] == "https://integrate.api.nvidia.com/v1"
    assert kwargs["extra_body"] == {"chat_template_kwargs": {"thinking": False}}


def test_llm_api_key_configured_for_nvidia(monkeypatch):
    monkeypatch.setattr(llm.settings, "agent_llm_provider", "nvidia")
    monkeypatch.setattr(llm.settings, "nvidia_api_key", "nvapi-test")
    assert llm.llm_api_key_configured() is True

    monkeypatch.setattr(llm.settings, "nvidia_api_key", "")
    assert llm.llm_api_key_configured() is False


def test_auto_prefers_gemini_over_nvidia_when_gemini_key_set(monkeypatch):
    monkeypatch.setattr(llm.settings, "agent_llm_provider", "auto")
    monkeypatch.setattr(llm.settings, "gemini_api_key", "gk-test")
    monkeypatch.setattr(llm.settings, "nvidia_api_key", "nvapi-test")

    assert llm.active_llm_provider() == "gemini"
    assert llm.llm_api_key_configured() is True


def test_resolve_model_id_uses_gemini_model_when_gemini_active(monkeypatch):
    monkeypatch.setattr(llm.settings, "agent_llm_provider", "gemini")
    monkeypatch.setattr(llm.settings, "gemini_api_key", "gk-test")
    monkeypatch.setattr(llm.settings, "agent_gemini_model_name", "gemini-2.5-flash")
    monkeypatch.setattr(llm.settings, "agent_gemini_researcher_model_name", "")
    # OpenRouter-style slug must NOT leak through when gemini is active.
    monkeypatch.setattr(llm.settings, "agent_researcher_model_name", "minimax/m2.5")

    assert llm.resolve_model_id() == "gemini-2.5-flash"
    assert llm.resolve_model_id(researcher=True) == "gemini-2.5-flash"

    monkeypatch.setattr(
        llm.settings, "agent_gemini_researcher_model_name", "gemini-3-pro"
    )
    assert llm.resolve_model_id(researcher=True) == "gemini-3-pro"


def test_build_agent_model_returns_gemini_and_rotates_keys(monkeypatch):
    monkeypatch.setattr(llm.settings, "agent_llm_provider", "gemini")
    monkeypatch.setattr(llm.settings, "gemini_api_key", "gk-a, gk-b")
    monkeypatch.setattr(llm.settings, "agent_gemini_model_name", "gemini-2.5-flash")
    llm._ROTATORS.clear()

    with patch("agno.models.google.Gemini") as mock_gemini:
        llm.build_agent_model()
        llm.build_agent_model()
        llm.build_agent_model()

    used_keys = [c.kwargs["api_key"] for c in mock_gemini.call_args_list]
    assert used_keys == ["gk-a", "gk-b", "gk-a"]
    assert all(c.kwargs["id"] == "gemini-2.5-flash" for c in mock_gemini.call_args_list)


def test_build_agent_model_raises_when_gemini_selected_without_key(monkeypatch):
    monkeypatch.setattr(llm.settings, "agent_llm_provider", "gemini")
    monkeypatch.setattr(llm.settings, "gemini_api_key", None)

    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        llm.build_agent_model()


def test_production_rejects_invalid_voyage_embedding_dimension():
    from backend.core.config import Settings, validate_production_settings

    s = Settings(
        debug=False,
        database_url="postgresql://localhost/db",
        voyage_api_key="vk_test",
        embedding_version="v2",
        embedding_dimension=1536,
        cors_allow_origins="https://app.example",
    )
    try:
        validate_production_settings(s)
        raised = False
    except ValueError as exc:
        raised = True
        assert "1536" in str(exc)
        assert "1024" in str(exc)
    assert raised
