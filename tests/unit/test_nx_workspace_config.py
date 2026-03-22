from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_root_package_json_contains_nx_and_scripts() -> None:
    package_json = _load_json(PROJECT_ROOT / "package.json")

    assert "nx" in package_json["devDependencies"]
    assert (
        package_json["scripts"]["dev"]
        == "nx run-many --target=dev --projects=api,agent,web --parallel=3"
    )
    assert package_json["scripts"]["nx:graph"] == "nx graph"


def test_nx_json_marks_dev_as_long_running() -> None:
    nx_json = _load_json(PROJECT_ROOT / "nx.json")

    target_defaults = nx_json["targetDefaults"]
    assert "dev" in target_defaults
    assert target_defaults["dev"]["cache"] is False


def test_project_dev_commands_match_existing_entrypoints() -> None:
    app_project = _load_json(PROJECT_ROOT / "app" / "project.json")
    agent_project = _load_json(PROJECT_ROOT / "agent" / "project.json")
    web_project = _load_json(PROJECT_ROOT / "web" / "project.json")

    app_dev_target = app_project["targets"]["dev"]
    agent_dev_target = agent_project["targets"]["dev"]
    web_dev_target = web_project["targets"]["dev"]

    assert app_dev_target["executor"] == "nx:run-commands"
    assert app_dev_target["options"]["command"] == (
        "uv run --package agentbook uvicorn app.main:app --reload"
    )

    assert agent_dev_target["executor"] == "nx:run-commands"
    assert agent_dev_target["options"]["cwd"] == "{workspaceRoot}"
    assert agent_dev_target["options"]["command"] == (
        "env -u DATABASE_URL uv run --package agentbook-agent -m agent.src.main"
    )

    assert web_dev_target["executor"] == "nx:run-commands"
    assert web_dev_target["options"]["command"] == "pnpm dev"
