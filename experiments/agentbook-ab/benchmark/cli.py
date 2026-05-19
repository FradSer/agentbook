#!/usr/bin/env python
"""Unified CLI for agentbook A/B benchmark v2.

  uv run python -m benchmark survey
  uv run python -m benchmark manifest eval-v2
  uv run python -m benchmark simulate-corpus
  uv run python -m benchmark prompts --preset eval-v2
  uv run python -m benchmark prepare --prompts prompts.v2.json
  uv run python -m benchmark score --preset eval-v2
  uv run python -m benchmark api-pipeline        # seed API + RAG prompts + prepare (2 arms)
  uv run python -m benchmark pipeline eval-v2    # manifest slice + api-pipeline
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
    argv = ["build_prompts.py", "--manifest", str(manifest), "-o", str(args.output)]
    if getattr(args, "use_api", False):
        argv.extend(["--use-api", "--api-url", args.api_url])
    _run_script(*argv)


def cmd_api_pipeline(args: argparse.Namespace) -> None:
    """Seed agentbook API → verify → RAG prompts → prepare (control + good only)."""
    api_url = args.api_url
    _run_script("build_seed_corpus.py", "--manifest", str(args.manifest))
    _run_script(
        "seed_agentbook.py",
        "--base-url",
        api_url,
        "--corpus",
        str(ROOT / "_oracle" / "corpus.seed.json"),
        "--force",
    )
    _run_script(
        "verify_agentbook_seed.py",
        "--manifest",
        str(args.manifest),
        "--base-url",
        api_url,
    )
    prompts_out = ROOT / "prompts.api.json"
    cells_out = ROOT / "cells_api.json"
    _run_script(
        "build_prompts.py",
        "--manifest",
        str(args.manifest),
        "--use-api",
        "--api-url",
        api_url,
        "-o",
        str(prompts_out),
    )
    _run_script("reset_runs.py", "--manifest", str(args.manifest), "--arms", "control", "good")
    _run_script(
        "prepare_cells.py",
        "--prompts",
        str(prompts_out),
        "-o",
        str(cells_out),
    )
    n = len(json.loads(cells_out.read_text()))
    print(f"\nAPI pipeline ready: {n} cells (control + good)")
    print(f"  prompts -> {prompts_out}")
    print(f"  cells   -> {cells_out}")
    print("Run agents, then: uv run python score.py control good -o results.api.json")


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
    """Write manifest slice, then run api-pipeline (seed + RAG + prepare)."""
    preset = args.preset
    manifest_out = DEFAULT_MANIFEST.parent / f"manifest.{preset}.json"
    results_out = ROOT / f"results.{preset}.json"

    cmd_manifest(
        argparse.Namespace(
            preset=preset,
            manifest=DEFAULT_MANIFEST,
            output=manifest_out,
            dry_run=False,
        )
    )
    cmd_api_pipeline(
        argparse.Namespace(manifest=manifest_out, api_url=args.api_url)
    )
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

    p = sub.add_parser("prompts", help="Build prompts JSON (requires --use-api)")
    p.add_argument("--preset", type=str, default="")
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    p.add_argument("-o", "--output", type=Path, default=ROOT / "prompts.api.json")
    p.add_argument("--use-api", action="store_true", default=True)
    p.add_argument("--api-url", default="http://127.0.0.1:8078")
    p.set_defaults(func=cmd_prompts, manifest_set=False)

    api = sub.add_parser("api-pipeline", help="Seed + RAG prompts + prepare (2 arms)")
    api.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    api.add_argument("--api-url", default="http://127.0.0.1:8078")
    api.set_defaults(func=cmd_api_pipeline)

    pr = sub.add_parser("prepare", help="Reset runs + prepare cell workspaces")
    pr.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    pr.add_argument("--prompts", type=Path, required=True)
    pr.add_argument("-o", "--cells", type=Path, default=ROOT / "cells.json")
    pr.add_argument("--reset", action="store_true", default=True)
    pr.set_defaults(func=cmd_prepare)

    sc = sub.add_parser("score", help="Grade runs")
    sc.add_argument("arms", nargs="*", default=["control", "good"])
    sc.add_argument("--preset", type=str, default="")
    sc.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    sc.add_argument("-o", "--output", type=Path)
    sc.set_defaults(func=cmd_score, manifest_set=False)

    pl = sub.add_parser("pipeline", help="manifest slice + api-pipeline")
    pl.add_argument("preset", default="eval-v2")
    pl.add_argument("--api-url", default="http://127.0.0.1:8078")
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
