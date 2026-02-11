from __future__ import annotations

import ast
from pathlib import Path

from shared.config import SharedSettings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read_env_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        keys.add(stripped.split("=", 1)[0].strip())
    return keys


def _class_assigns_model_config(path: Path, class_name: str) -> bool:
    module = ast.parse(path.read_text(encoding="utf-8"))
    for node in module.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                if any(
                    isinstance(target, ast.Name) and target.id == "model_config"
                    for target in stmt.targets
                ):
                    return True
            if isinstance(stmt, ast.AnnAssign):
                if (
                    isinstance(stmt.target, ast.Name)
                    and stmt.target.id == "model_config"
                ):
                    return True
        return False
    raise AssertionError(f"Class {class_name} not found in {path}")


def test_shared_settings_uses_absolute_root_env_file() -> None:
    assert SharedSettings.model_config.get("env_file") == str(PROJECT_ROOT / ".env")


def test_backend_settings_does_not_define_model_config() -> None:
    path = PROJECT_ROOT / "app/core/config.py"
    assert _class_assigns_model_config(path, "Settings") is False


def test_agent_settings_does_not_define_model_config() -> None:
    path = PROJECT_ROOT / "agent/src/config.py"
    assert _class_assigns_model_config(path, "AgentSettings") is False


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
        "AGENT_QUALITY_THRESHOLD",
        "LOG_LEVEL",
    }

    assert expected_agent_keys.issubset(env_keys)


def test_agent_env_example_removed() -> None:
    assert not (PROJECT_ROOT / "agent/.env.example").exists()
