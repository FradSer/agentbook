"""Detect when a stats aggregate is stale relative to the runs_v2/ samples.

aggregate.py embeds a source_fingerprint built here; this module recomputes it
from the live tree so any drift between the published report and the actual run
artifacts is loud and detectable -- replacing the silent summary != runs bug.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.sandbox import RUNS_V2  # noqa: E402


def _repo_head(run_dir: Path) -> str:
    repo = run_dir / "repo"
    if not repo.is_dir():
        return "no-repo"
    r = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True
    )
    return r.stdout.strip() or "no-head"


def fingerprint(runs_v2: Path = RUNS_V2) -> str:
    h = hashlib.sha256()
    if not runs_v2.is_dir():
        return "empty"
    for result in sorted(runs_v2.glob("*/result.json")):
        run_dir = result.parent
        h.update(run_dir.name.encode())
        h.update(str(result.stat().st_mtime_ns).encode())
        h.update(_repo_head(run_dir).encode())
    return h.hexdigest()[:24]


def check(aggregate_path: Path) -> bool:
    """True if the aggregate's stored fingerprint matches the live tree."""
    if not aggregate_path.exists():
        return False
    stored = json.loads(aggregate_path.read_text()).get("source_fingerprint")
    return stored == fingerprint()


if __name__ == "__main__":
    agg = ROOT / "runs_v2" / "_aggregate.json"
    live = fingerprint()
    ok = check(agg)
    print(f"live fingerprint: {live}")
    print(f"aggregate fresh: {ok}")
