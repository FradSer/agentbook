"""Agent runtime regression tests."""

import importlib
from unittest import mock
from uuid import uuid4


class DummyService:
    def __init__(self) -> None:
        self.updates: list[dict] = []

    def update_review(self, **kwargs):
        self.updates.append(kwargs)

    def delete_content(self, _content_id):
        return None


def test_get_reviewer_tools_returns_callable_tools() -> None:
    tools_module = importlib.import_module("agent.src.tools")
    tool_builders = tools_module.get_reviewer_tools(DummyService())

    assert len(tool_builders) == 2
    result = tool_builders[0].entrypoint(
        content_id=str(uuid4()),
        reason="ok",
    )
    assert "approved" in result


def test_pgvector_is_available_in_agent_runtime() -> None:
    sqlalchemy_models = importlib.import_module(
        "backend.infrastructure.persistence.sqlalchemy_models"
    )
    assert sqlalchemy_models.Vector is not None


def test_main_exits_when_openrouter_api_key_missing() -> None:
    main_module = importlib.import_module("agent.src.main")
    original_database_url = main_module.settings.database_url
    original_openrouter_api_key = main_module.settings.openrouter_api_key
    main_module.settings.database_url = "postgresql://example"
    main_module.settings.openrouter_api_key = None

    try:
        with mock.patch.object(main_module, "create_engine") as create_engine_mock:
            main_module.main()
        create_engine_mock.assert_not_called()
    finally:
        main_module.settings.database_url = original_database_url
        main_module.settings.openrouter_api_key = original_openrouter_api_key
