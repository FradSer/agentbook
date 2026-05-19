#!/usr/bin/env python
"""Report which benchmark cells have an agent fix commit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cell_workspace import RUNS, has_agent_fix

ROOT = Path(__file__).parent


def has_fix(iid: str, arm: str) -> bool:
    return has_agent_fix(RUNS / f"{iid}__{arm}" / "repo")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", type=Path, default=ROOT / "cells_api.json")
    ap.add_argument("--arm", choices=("control", "good", "all"), default="all")
    ap.add_argument("--pending-only", action="store_true")
    args = ap.parse_args()

    cells = json.loads(args.cells.read_text())
    pending: list[list[str]] = []
    done = 0
    for iid, arm in cells:
        if args.arm != "all" and arm != args.arm:
            continue
        ok = has_fix(iid, arm)
        if ok:
            done += 1
        elif args.pending_only:
            pending.append([iid, arm])
        elif not args.pending_only:
            print(f"{'ok' if ok else 'pending':8s} {iid}__{arm}")

    total = sum(1 for _, a in cells if args.arm in ("all", a))
    print(f"\n{done}/{total} with fix commit (arm={args.arm})", file=sys.stderr)
    if args.pending_only:
        json.dump(pending, sys.stdout, indent=2)
        print(file=sys.stderr)


if __name__ == "__main__":
    main()
