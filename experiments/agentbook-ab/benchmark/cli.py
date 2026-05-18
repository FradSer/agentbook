#!/usr/bin/env python
"""Unified CLI for agentbook A/B benchmark v2.

  uv run python -m benchmark survey
  uv run python -m benchmark manifest eval-v2
  uv run python -m benchmark simulate-corpus
  uv run python -m benchmark prompts --preset eval-v2
  uv run python -m benchmark prepare --prompts prompts.v2.json
  uv run python -m benchmark score --preset eval-v2
  uv run python -m benchmark pipeline eval-v2   # simulate + manifest + prompts + prepare
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

EXP_ROOT = Path(__file__).resolve().parent.parent
if str(EXP_ROOT) not in sys.path:
    sys.path.insert(0, str(EXP_ROOT))

from benchmark.datasets import print_survey  # noqa: E402
from benchmark.manifest import filter_manifest, write_manifest  # noqa: E402
from benchmark.paths import CORPUS_SIMULATED, DEFAULT_MANIFEST, EXP_ROOT as ROOT, RUNS  # noqa: E402


def _run_script(script: str, *args: str) -> None:
    cmd = [sys.executable, str(ROOT / script), *args]
    subprocess.run(cmd, cwd=ROOT, check=True)


def cmd_survey(_: argparse.Namespace) -> None:
    print_survey()


def cmd_manifest(args: argparse.Namespace) -> None:
    filtered = filter_manifest(args.preset, manifest_path=args.manifest)
    out = args.output or (DEFAULT_MANIFEST.parent / f"manifest.{args.preset}.json")
    if not args.dry_run:
        out.write_text(json.dumps(filtered, indent=2) + "\n")
    print(f"preset={args.preset}  tasks={len(filtered)}  -> {out.name}")
    if args.dry_run:
        for e in filtered[:5]:
            print(f"  {e['instance_id']}")
        if len(filtered) > 5:
            print(f"  ... +{len(filtered) - 5} more")


def cmd_simulate_corpus(args: argparse.Namespace) -> None:
    _run_script(
        "simulate_corpus.py",
        "--manifest",
        str(args.manifest),
        "-o",
        str(args.output),
    )


def cmd_prompts(args: argparse.Namespace) -> None:
    manifest = args.manifest
    if args.preset and not args.manifest_set:
        manifest = DEFAULT_MANIFEST.parent / f"manifest.{args.preset}.json"
    argv = [
        "build_prompts.py",
        "--manifest",
        str(manifest),
        "--corpus",
        str(args.corpus),
        "-o",
        str(args.output),
    ]
    if args.good_mode:
        argv.extend(["--good-mode", args.good_mode])
    _run_script(*argv)


def cmd_prepare(args: argparse.Namespace) -> None:
    if args.reset:
        _run_script(
            "reset_runs.py",
            "--manifest",
            str(args.manifest),
        )
    _run_script(
        "prepare_cells.py",
        "--prompts",
        str(args.prompts),
        "-o",
        str(args.cells),
    )


def cmd_score(args: argparse.Namespace) -> None:
    manifest = args.manifest
    if args.preset and not args.manifest_set:
        manifest = DEFAULT_MANIFEST.parent / f"manifest.{args.preset}.json"
    out = args.output
    if out is None and args.preset:
        out = ROOT / f"results.{args.preset}.json"
    argv = [
        "score.py",
        *args.arms,
        "--manifest",
        str(manifest),
    ]
    if out:
        argv.extend(["-o", str(out)])
    _run_script(*argv)


def cmd_pipeline(args: argparse.Namespace) -> None:
    preset = args.preset
    manifest_out = DEFAULT_MANIFEST.parent / f"manifest.{preset}.json"
    prompts_out = ROOT / f"prompts.{preset}.json"
    cells_out = ROOT / f"cells_{preset}.json"
    results_out = ROOT / f"results.{preset}.json"

    cmd_manifest(
        argparse.Namespace(
            preset=preset,
            manifest=DEFAULT_MANIFEST,
            output=manifest_out,
            dry_run=False,
        )
    )
    cmd_simulate_corpus(
        argparse.Namespace(manifest=manifest_out, output=CORPUS_SIMULATED)
    )
    cmd_prompts(
        argparse.Namespace(
            preset=preset,
            manifest_set=True,
            manifest=manifest_out,
            corpus=CORPUS_SIMULATED,
            output=prompts_out,
            good_mode=args.good_mode,
        )
    )
    cmd_prepare(
        argparse.Namespace(
            reset=True,
            manifest=manifest_out,
            prompts=prompts_out,
            cells=cells_out,
        )
    )
    print(f"\nPipeline ready: {len(json.loads(cells_out.read_text()))} cells")
    print(f"  manifest -> {manifest_out}")
    print(f"  prompts  -> {prompts_out}")
    print(f"  cells    -> {cells_out}")
    print("Run agents per AGENT_CELL_RULES.md, then:")
    print(f"  uv run python -m benchmark score --preset {preset} -o {results_out}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Agentbook A/B benchmark v2")
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("survey", help="Print dataset catalog").set_defaults(func=cmd_survey)

    m = sub.add_parser("manifest", help="Write filtered manifest")
    m.add_argument("preset", choices=sorted(__import__("benchmark.manifest", fromlist=["PRESETS"]).PRESETS))
    m.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    m.add_argument("-o", "--output", type=Path)
    m.add_argument("--dry-run", action="store_true")
    m.set_defaults(func=cmd_manifest)

    s = sub.add_parser("simulate-corpus", help="Build corpus.simulated.json")
    s.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    s.add_argument("-o", "--output", type=Path, default=CORPUS_SIMULATED)
    s.set_defaults(func=cmd_simulate_corpus)

    p = sub.add_parser("prompts", help="Build prompts JSON")
    p.add_argument("--preset", type=str, default="")
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p.add_argument("--corpus", type=Path, default=CORPUS_SIMULATED)
    p.add_argument("-o", "--output", type=Path, default=ROOT / "prompts.json")
    p.add_argument(
        "--good-mode",
        choices=("simulated", "hand-only", "hand-then-simulated"),
        default="hand-then-simulated",
        help="Good-arm corpus source policy",
    )
    p.set_defaults(func=cmd_prompts, manifest_set=False)

    pr = sub.add_parser("prepare", help="Reset runs + prepare cell workspaces")
    pr.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    pr.add_argument("--prompts", type=Path, required=True)
    pr.add_argument("-o", "--cells", type=Path, default=ROOT / "cells.json")
    pr.add_argument("--reset", action="store_true", default=True)
    pr.set_defaults(func=cmd_prepare)

    sc = sub.add_parser("score", help="Grade runs")
    sc.add_argument("arms", nargs="*", default=["control", "good", "bad"])
    sc.add_argument("--preset", type=str, default="")
    sc.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    sc.add_argument("-o", "--output", type=Path)
    sc.set_defaults(func=cmd_score, manifest_set=False)

    pl = sub.add_parser("pipeline", help="manifest + corpus + prompts + prepare")
    pl.add_argument("preset", default="eval-v2")
    pl.add_argument(
        "--good-mode",
        default="hand-then-simulated",
        choices=("simulated", "hand-only", "hand-then-simulated"),
    )
    pl.set_defaults(func=cmd_pipeline)

    cl = sub.add_parser("cleanup", help="Remove stale runs, results, oracle shortcuts")
    cl.add_argument("--dry-run", action="store_true")
    cl.add_argument("--keep-runs", action="store_true")
    cl.set_defaults(
        func=lambda a: __import__("subprocess").run(
            [sys.executable, str(ROOT / "cleanup_experiment.py")]
            + (["--dry-run"] if a.dry_run else [])
            + (["--keep-runs"] if a.keep_runs else []),
            cwd=ROOT,
            check=True,
        )
    )

    args = ap.parse_args()
    if hasattr(args, "manifest_set") is False:
        args.manifest_set = bool(getattr(args, "manifest", None) != DEFAULT_MANIFEST)
    args.func(args)


if __name__ == "__main__":
    main()
