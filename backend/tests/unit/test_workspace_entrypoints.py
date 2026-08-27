from __future__ import annotations

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


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
            "import backend.core.config",
        ]
    )
    # The Pi worker is a Node workspace package, not a Python module, so its
    # entrypoint is verified statically rather than by importing it. Running
    # `pnpm --filter @agentbook/pi-worker build` here would shell out to pnpm,
    # which is not on PATH in the backend-only CI job (FileNotFoundError). The
    # frontend job exercises the actual tsc build; here we only assert the
    # package manifest and tsconfig exist so the workspace resolves.
    import json

    agent_pkg = PROJECT_ROOT / "agent" / "package.json"
    assert agent_pkg.exists(), f"agent/package.json missing at {agent_pkg}"
    pkg = json.loads(agent_pkg.read_text())
    assert pkg.get("name") == "@agentbook/pi-worker"
    assert "build" in pkg.get("scripts", {}), "agent build script missing"
    assert (PROJECT_ROOT / "agent" / "tsconfig.json").exists()
