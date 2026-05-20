#!/usr/bin/env python
"""Collect cells that failed with api_error for a later OpenRouter-only retry.

Reads ``openrouter_run_results.json`` (or ``-o`` path from the last run) and writes
``cells_api_errors.json`` as ``[[instance_id, arm], ...]``.

  uv run python collect_openrouter_errors.py
  uv run python collect_openrouter_errors.py --merge

After collection, retry with:
  ./run_openrouter_benchmark.sh retry-errors
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).parent
DEFAULT_RESULTS = ROOT / "openrouter_run_results.json"
OUT = ROOT / "cells_api_errors.json"


def from_results(path: Path) -> list[list[str]]:
    if not path.is_file():
        return []
    rows = json.loads(path.read_text())
    if isinstance(rows, dict):
        rows = rows.get("results", [])
    out: list[list[str]] = []
    for row in rows:
        if row.get("status") == "api_error":
            out.append([row["instance_id"], row["arm"]])
    return out


def dedupe(cells: list[list[str]]) -> list[list[str]]:
    seen: set[tuple[str, str]] = set()
    unique: list[list[str]] = []
    for iid, arm in cells:
        key = (iid, arm)
        if key in seen:
            continue
        seen.add(key)
        unique.append([iid, arm])
    return sorted(unique, key=lambda x: (x[0], x[1]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    ap.add_argument("-o", "--output", type=Path, default=OUT)
    ap.add_argument(
        "--merge",
        action="store_true",
        help="Union with existing cells_api_errors.json",
    )
    args = ap.parse_args()

    cells = from_results(args.results)
    if args.merge and args.output.is_file():
        cells.extend(json.loads(args.output.read_text()))
    cells = dedupe(cells)

    args.output.write_text(json.dumps(cells, indent=2) + "\n")
    print(f"api_error cells: {len(cells)} -> {args.output}")
    for iid, arm in cells:
        print(f"  {iid}__{arm}")


if __name__ == "__main__":
    main()
