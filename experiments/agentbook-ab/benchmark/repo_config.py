"""Repo configuration for multi-repo SWE-bench Verified no-Docker substrate."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PY = ROOT / ".venv" / "bin" / "python"

# Repos included in the benchmark, with version filters and pilot caps.
REPOS: dict[str, dict] = {
    "sympy/sympy": {
        "versions": {
            "1.0",
            "1.1",
            "1.2",
            "1.4",
            "1.5",
            "1.6",
            "1.7",
            "1.8",
            "1.9",
            "1.10",
            "1.11",
            "1.12",
        },
        "max_instances": None,
        "requirements": [ROOT / "bench_requirements.txt"],
        "editable_install": False,
    },
    "scikit-learn/scikit-learn": {
        "versions": {"1.3"},
        "max_instances": 15,
        "requirements": [
            ROOT / "bench_requirements.txt",
            ROOT / "bench_requirements.sklearn.txt",
        ],
        "editable_install": True,
        "pythonpath": False,
    },
    "pytest-dev/pytest": {
        "versions": {"5.4", "6.0", "6.2", "6.3", "7.2"},
        "max_instances": 15,
        "requirements": [
            ROOT / "bench_requirements.txt",
            ROOT / "bench_requirements.pytest.txt",
        ],
        "editable_install": False,
        "pythonpath": True,
    },
}

SYMPY_ONLY = {"sympy/sympy"}
MULTIREPO_PILOT = {
    "sympy/sympy",
    "scikit-learn/scikit-learn",
    "pytest-dev/pytest",
}


def repo_cfg(repo: str) -> dict:
    try:
        return REPOS[repo]
    except KeyError as exc:
        raise KeyError(f"unknown benchmark repo: {repo!r}") from exc


def install_venv_requirements(repos: set[str]) -> None:
    """Install pinned deps into .venv for the given repos (once per requirements file)."""
    import subprocess

    if not VENV_PY.is_file():
        raise RuntimeError(
            f"benchmark venv missing: {VENV_PY.parent.parent}\n"
            "Run: uv venv .venv --python 3.10 && uv pip install -r bench_requirements.txt"
        )

    seen: set[Path] = set()
    for repo in repos:
        for req in repo_cfg(repo)["requirements"]:
            if req in seen or not req.is_file():
                continue
            seen.add(req)
            print(f"  uv pip install -r {req.name} ...", flush=True)
            r = subprocess.run(
                [
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    str(VENV_PY),
                    "-r",
                    str(req),
                ],
                capture_output=True,
                text=True,
            )
            if r.returncode != 0:
                raise RuntimeError(
                    f"pip install failed for {req.name}: {r.stderr.strip()[:500]}"
                )


def workspace_env(repo: str, workspace: Path) -> dict[str, str]:
    """Return extra env vars for pytest in a repo workspace."""
    import os

    env = os.environ.copy()
    if repo_cfg(repo).get("pythonpath"):
        prefix = str(workspace.resolve())
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = prefix if not existing else f"{prefix}{os.pathsep}{existing}"
    return env


def install_workspace(repo: str, workspace: Path) -> tuple[bool, str]:
    """Prepare a task workspace for pytest (editable install when needed)."""
    import subprocess

    cfg = repo_cfg(repo)
    if not cfg.get("editable_install"):
        return True, "no editable install required"

    r = subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(VENV_PY),
            "-e",
            str(workspace),
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if r.returncode != 0:
        return False, r.stderr.strip()[:300]
    return True, "editable install ok"
