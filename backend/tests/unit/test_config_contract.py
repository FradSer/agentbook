from __future__ import annotations

from pathlib import Path

import pytest

from shared.config import SharedSettings

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _read_env_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        keys.add(stripped.split("=", 1)[0].strip())
    return keys


def _shared_env_file() -> str | None:
    return SharedSettings.model_config.get("env_file")


def _backend_env_file() -> str | None:
    from backend.core.config import Settings

    return Settings.model_config.get("env_file")


def _agent_env_file() -> str | None:
    from agent.src.config import AgentSettings

    return AgentSettings.model_config.get("env_file")


@pytest.mark.parametrize(
    "settings_loader",
    [
        pytest.param(_shared_env_file, id="shared"),
        pytest.param(_backend_env_file, id="backend"),
        pytest.param(_agent_env_file, id="agent"),
    ],
)
def test_given_runtime_settings_when_reading_env_config_then_all_layers_use_project_root_env(
    settings_loader,
) -> None:
    settings_env_file = settings_loader()
    assert settings_env_file == str(PROJECT_ROOT / ".env")


@pytest.mark.parametrize("relative_path", ["agent/src/config.py", "agent/src/main.py"])
def test_given_agent_runtime_module_when_scanning_source_then_no_sys_path_insert_is_used(
    relative_path: str,
) -> None:
    source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
    assert "sys.path.insert" not in source


def test_given_root_env_example_when_reading_keys_then_required_agent_keys_exist() -> (
    None
):
    env_keys = _read_env_keys(PROJECT_ROOT / ".env.example")

    expected_agent_keys = {
        "AGENT_POLL_INTERVAL",
        "AGENT_BATCH_SIZE",
        "AGENT_MAX_CYCLE_SECONDS",
        "AGENT_CONTINUE_DELAY_SECONDS",
        "AGENT_BACKLOG_RETRY_DELAY_SECONDS",
        "AGENT_MODEL_NAME",
        "AGENT_RESEARCHER_MODEL_NAME",
        "AGENT_LLM_PROVIDER",
        "NVIDIA_API_KEY",
        "NVIDIA_BASE_URL",
        "CF_AIG_URL",
        "CF_AIG_TOKEN",
        "LOG_LEVEL",
    }

    assert expected_agent_keys.issubset(env_keys)


def test_given_repo_layout_when_checking_agent_env_example_then_file_is_removed() -> (
    None
):
    assert not (PROJECT_ROOT / "agent/.env.example").exists()
