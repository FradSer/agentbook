from __future__ import annotations

from pathlib import Path

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


def test_shared_settings_reads_root_env() -> None:
    env_file = SharedSettings.model_config.get("env_file")
    assert env_file == str(PROJECT_ROOT / ".env")


def test_backend_settings_inherits_root_env() -> None:
    from backend.core.config import Settings

    assert Settings.model_config.get("env_file") == str(PROJECT_ROOT / ".env")


def test_agent_settings_inherits_root_env() -> None:
    from agent.src.config import AgentSettings

    assert AgentSettings.model_config.get("env_file") == str(PROJECT_ROOT / ".env")


def test_agent_runtime_modules_do_not_call_sys_path_insert() -> None:
    for relative_path in ("agent/src/config.py", "agent/src/main.py"):
        source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        assert "sys.path.insert" not in source


def test_root_env_example_contains_agent_keys() -> None:
    env_keys = _read_env_keys(PROJECT_ROOT / ".env.example")

    expected_agent_keys = {
        "AGENT_POLL_INTERVAL",
        "AGENT_BATCH_SIZE",
        "AGENT_MAX_CYCLE_SECONDS",
        "AGENT_CONTINUE_DELAY_SECONDS",
        "AGENT_BACKLOG_RETRY_DELAY_SECONDS",
        "AGENT_MODEL_NAME",
        "LOG_LEVEL",
    }

    assert expected_agent_keys.issubset(env_keys)


def test_agent_env_example_removed() -> None:
    assert not (PROJECT_ROOT / "agent/.env.example").exists()
