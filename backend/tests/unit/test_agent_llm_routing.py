"""Tests for agent LLM provider routing."""

from __future__ import annotations

from unittest.mock import patch

from agent.src import llm


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
    monkeypatch.setattr(llm.settings, "agent_researcher_model_name", "minimax/minimax-m2.5")

    assert llm.resolve_model_id(researcher=True) == (
        "google-ai-studio/gemini-3.1-flash-lite-preview"
    )


def test_resolve_model_id_keeps_researcher_when_cf_not_configured(monkeypatch):
    monkeypatch.setattr(llm.settings, "cf_aig_url", "")
    monkeypatch.setattr(llm.settings, "cf_aig_token", "")
    monkeypatch.setattr(llm.settings, "agent_researcher_model_name", "minimax/minimax-m2.5")

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
