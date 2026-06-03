"""Tests for agent LLM provider routing."""

from __future__ import annotations

from agent.src import llm
def test_resolve_model_id_falls_back_from_minimax_on_cf_gateway(monkeypatch):
    monkeypatch.setattr(llm.settings, "agent_llm_provider", "auto")
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

