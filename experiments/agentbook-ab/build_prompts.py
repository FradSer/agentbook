#!/usr/bin/env python
"""Build prompts for the two-arm A/B (control + good via agentbook API RAG).

Good arm: calls GET /v1/search on a running agentbook instance (no inline corpus).
Control arm: bug description only.

Run:
  # Start agentbook API, then seed + build:
  uv run python experiments/agentbook-ab/seed_agentbook.py
  uv run python experiments/agentbook-ab/build_prompts.py --use-api
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).parent
TASKS = ROOT / "tasks"
ORACLE = ROOT / "_oracle"
MANIFEST = TASKS / "manifest.json"
RUNS = ROOT / "runs"

CONTROL_PROMPT = """You are a coding agent tasked with fixing a bug in a Python project.

## Bug Description

{bug_description}

## Instructions

1. Read the bug description carefully.
2. Explore the source code in the repository to understand the problem.
3. Identify the root cause of the bug.
4. Make minimal, targeted changes to fix the bug.
5. Do NOT edit any test files - only fix source code.
6. Your fix should be as minimal as possible.

The repository is at: {repo_path}

Important: Only modify source files (not test files). Focus on the minimal fix that addresses the root cause."""

GOOD_API_PROMPT = """You are a coding agent tasked with fixing a bug in a Python project.

## Bug Description

{bug_description}

## Agentbook memory (live API retrieval)

The hint below was retrieved from the **agentbook** shared memory layer using the
production search API (`GET /v1/search`, hybrid RAG). It is not copied from a local
oracle file. Verify it against the actual source before applying.

{agentbook_recall}

## Instructions

1. Read the bug description and the agentbook recall above.
2. Explore the source code to verify whether the recalled solution matches this instance.
3. If the recall is relevant, use it to guide your fix; otherwise rely on your own analysis.
4. Make minimal, targeted changes to fix the bug.
5. Do NOT edit any test files - only fix source code.

The repository is at: {repo_path}

Important: Only modify source files (not test files)."""


def main() -> None:
    ap = argparse.ArgumentParser(description="Build per-cell prompts (control + good)")
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("-o", "--output", type=Path, default=ROOT / "prompts.api.json")
    ap.add_argument(
        "--use-api",
        action="store_true",
        help="Good arm: fetch hints via GET /v1/search (requires running agentbook)",
    )
    ap.add_argument(
        "--api-url",
        default="http://127.0.0.1:8078",
        help="Agentbook API base URL for --use-api",
    )
    ap.add_argument(
        "--search-limit",
        type=int,
        default=3,
        help="Top-k for /v1/search per task",
    )
    args = ap.parse_args()

    if not args.use_api:
        raise SystemExit(
            "This benchmark requires --use-api (good arm uses agentbook RAG). "
            "Start agentbook, run seed_agentbook.py, then build_prompts.py --use-api"
        )

    import sys

    sys.path.insert(0, str(ROOT))
    from benchmark.agentbook_client import (  # noqa: WPS433
        AgentbookClient,
        build_search_query,
        format_recall_for_prompt,
    )

    client = AgentbookClient(args.api_url)
    try:
        client.ping()
        client.ensure_agent()
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(
            f"Cannot reach agentbook at {args.api_url}: {exc}\n"
            "Start API: DEMO_MODE=1 uv run uvicorn backend.main:app --port 8078"
        ) from exc

    manifest = json.loads(args.manifest.read_text())
    prompts: dict = {}
    recalls_dir = ROOT / "recalls"
    recalls_dir.mkdir(exist_ok=True)

    for entry in manifest:
        iid = entry["instance_id"]
        bug_text = (TASKS / iid / "BUG.md").read_text()
        repo_path = str((RUNS / f"{iid}__control" / "repo").resolve())

        prompts[f"{iid}__control"] = {
            "instance_id": iid,
            "arm": "control",
            "prompt": CONTROL_PROMPT.format(
                bug_description=bug_text,
                repo_path=str((RUNS / f"{iid}__control" / "repo").resolve()),
            ),
            "repo_path": str((RUNS / f"{iid}__control" / "repo").resolve()),
        }

        query, err_log = build_search_query(bug_text)
        payload = client.search(query, error_log=err_log, limit=args.search_limit)
        recall_md = format_recall_for_prompt(payload)
        (recalls_dir / f"{iid}.json").write_text(json.dumps(payload, indent=2) + "\n")

        good_repo = str((RUNS / f"{iid}__good" / "repo").resolve())
        prompts[f"{iid}__good"] = {
            "instance_id": iid,
            "arm": "good",
            "prompt": GOOD_API_PROMPT.format(
                bug_description=bug_text,
                agentbook_recall=recall_md,
                repo_path=good_repo,
            ),
            "repo_path": good_repo,
            "recall_query": query,
            "search_total": payload.get("total", 0),
        }

    client.close()

    args.output.write_text(json.dumps(prompts, indent=2) + "\n")
    n = len(manifest)
    print(f"Built {len(prompts)} prompts -> {args.output} (API RAG @ {args.api_url})")
    print(f"  control: {n}  good: {n}  recalls -> {recalls_dir}/")


if __name__ == "__main__":
    main()
