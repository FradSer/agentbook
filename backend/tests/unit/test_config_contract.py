from __future__ import annotations

from pathlib import Path

import pytest

from backend.core.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _read_env_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        keys.add(stripped.split("=", 1)[0].strip())
    return keys


def _backend_env_file() -> str | None:
    return Settings.model_config.get("env_file")


@pytest.mark.parametrize(
    "settings_loader",
    [pytest.param(_backend_env_file, id="backend")],
)
def test_given_runtime_settings_when_reading_env_config_then_all_layers_use_project_root_env(
    settings_loader,
) -> None:
    settings_env_file = settings_loader()
    assert settings_env_file == str(PROJECT_ROOT / ".env")


def test_given_root_env_example_when_reading_keys_then_gateway_keys_exist() -> None:
    env_keys = _read_env_keys(PROJECT_ROOT / ".env.example")
    assert {"AI_GATEWAY_BASE_URL", "AI_GATEWAY_ID", "AI_GATEWAY_AUTH_TOKEN"}.issubset(
        env_keys
    )
