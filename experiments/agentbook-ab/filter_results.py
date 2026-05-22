#!/usr/bin/env python
"""Filter score.py JSON output to a manifest subset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).parent


def main() -> None:
    ap = argparse.ArgumentParser(description="Filter results JSON to manifest tasks")
    ap.add_argument("results", type=Path, help="Input results JSON from score.py")
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()

    manifest_ids = {e["instance_id"] for e in json.loads(args.manifest.read_text())}
    rows = json.loads(args.results.read_text())
    filtered = [r for r in rows if r["instance_id"] in manifest_ids]
    args.output.write_text(json.dumps(filtered, indent=2) + "\n")
    print(f"filtered {len(filtered)} rows -> {args.output}")


if __name__ == "__main__":
    main()
