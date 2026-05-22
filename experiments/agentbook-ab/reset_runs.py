#!/usr/bin/env python
"""Delete run workspaces so a batch can start from pristine prepared repos."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
RUNS = ROOT / "runs"
DEFAULT_MANIFEST = ROOT / "tasks" / "manifest.json"


def _remove_tree(path: Path) -> None:
    if not path.exists():
        return
    shutil.rmtree(path, ignore_errors=True)
    if path.exists():
        shutil.rmtree(path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--arms", nargs="*", default=("control", "good"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text())
    removed = 0
    for entry in manifest:
        iid = entry["instance_id"]
        for arm in args.arms:
            d = RUNS / f"{iid}__{arm}"
            if d.exists():
                removed += 1
                if args.dry_run:
                    print(f"would remove {d}")
                else:
                    _remove_tree(d)
    print(f"{'would remove' if args.dry_run else 'removed'} {removed} run dirs")


if __name__ == "__main__":
    main()
