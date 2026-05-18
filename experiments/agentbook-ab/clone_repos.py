#!/usr/bin/env python
"""Clone upstream repos needed by the benchmark manifest (or full Verified set).

Clones into experiments/agentbook-ab/_repo/<short_name>/ with full git history
so `git archive <base_commit>` works in build_benchmark.py.

Run:
  uv run --with pandas python experiments/agentbook-ab/clone_repos.py
  uv run --with pandas python experiments/agentbook-ab/clone_repos.py --from-manifest
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "_data" / "verified.parquet"
REPO_DIR = ROOT / "_repo"
MANIFEST = ROOT / "tasks" / "manifest.json"

# GitHub slugs for every repo in SWE-bench Verified
UPSTREAM = {
    "astropy/astropy": "https://github.com/astropy/astropy.git",
    "django/django": "https://github.com/django/django.git",
    "matplotlib/matplotlib": "https://github.com/matplotlib/matplotlib.git",
    "mwaskom/seaborn": "https://github.com/mwaskom/seaborn.git",
    "pallets/flask": "https://github.com/pallets/flask.git",
    "psf/requests": "https://github.com/psf/requests.git",
    "pydata/xarray": "https://github.com/pydata/xarray.git",
    "pylint-dev/pylint": "https://github.com/pylint-dev/pylint.git",
    "pytest-dev/pytest": "https://github.com/pytest-dev/pytest.git",
    "scikit-learn/scikit-learn": "https://github.com/scikit-learn/scikit-learn.git",
    "sphinx-doc/sphinx": "https://github.com/sphinx-doc/sphinx.git",
    "sympy/sympy": "https://github.com/sympy/sympy.git",
}


def slug(repo: str) -> str:
    return repo.split("/")[-1]


def clone(repo: str, url: str) -> None:
    dest = REPO_DIR / slug(repo)
    if (dest / ".git").is_dir():
        print(f"  {repo} -> {dest} (exists)")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  cloning {repo} -> {dest} ...", flush=True)
    r = subprocess.run(
        ["git", "clone", "--filter=blob:none", url, str(dest)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"clone failed for {repo}: {r.stderr.strip()}")


def repos_from_manifest() -> list[str]:
    manifest = json.loads(MANIFEST.read_text())
    return sorted({e["repo"] for e in manifest})


def repos_from_parquet() -> list[str]:
    import pandas as pd

    df = pd.read_parquet(DATA)
    return sorted(df["repo"].unique())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--from-manifest",
        action="store_true",
        help="Only clone repos present in tasks/manifest.json",
    )
    ap.add_argument("--repo", action="append", help="Clone a single repo slug (owner/name)")
    args = ap.parse_args()

    if args.repo:
        wanted = args.repo
    elif args.from_manifest:
        if not MANIFEST.exists():
            raise SystemExit(f"manifest not found: {MANIFEST}")
        wanted = repos_from_manifest()
    else:
        if not DATA.exists():
            raise SystemExit(f"run fetch_verified.py first; missing {DATA}")
        wanted = repos_from_parquet()

    REPO_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Cloning {len(wanted)} repos into {REPO_DIR}\n")
    for repo in wanted:
        url = UPSTREAM.get(repo)
        if not url:
            print(f"  SKIP {repo} (no URL in UPSTREAM map)")
            continue
        clone(repo, url)
    print("\nDone.")


if __name__ == "__main__":
    main()
