from __future__ import annotations

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _assert_uv_run_import(command: list[str]) -> None:
    result = subprocess.run(
        command, cwd="/tmp", capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, (
        "Command failed:\n"
        f"{' '.join(command)}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def test_workspace_entrypoints_import_outside_repo() -> None:
    _assert_uv_run_import(
        [
            "uv",
            "run",
            "--project",
            str(PROJECT_ROOT),
            "--package",
            "agentbook",
            "python",
            "-c",
            "import app.core.config, shared.config",
        ]
    )
    _assert_uv_run_import(
        [
            "uv",
            "run",
            "--project",
            str(PROJECT_ROOT),
            "--package",
            "agentbook-agent",
            "python",
            "-c",
            "import agent.src.config",
        ]
    )
