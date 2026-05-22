#!/usr/bin/env python
"""Build per-cell prompts (control + good via API RAG + oracle upper bound)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent
TASKS = ROOT / "tasks"
ORACLE = ROOT / "_oracle"
MANIFEST = TASKS / "manifest.json"
RUNS = ROOT / "runs"
SEED_CORPUS = ORACLE / "corpus.seed.json"

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
2. Open the source files named in the hint and verify the diagnosis matches this instance.
3. Apply the minimal fix described in the hint and steps; adjust only if source differs.
4. Do NOT edit any test files - only fix source code.

The repository is at: {repo_path}

Important: Only modify source files (not test files)."""

ORACLE_PROMPT = """You are a coding agent tasked with fixing a bug in a Python project.

## Bug Description

{bug_description}

## Agentbook memory (oracle upper bound — direct accurate hint)

The hint below is the **verified accurate solution** for this exact task, injected
directly as an upper-bound baseline (not retrieved via search). Use it to guide your fix.

{agentbook_recall}

## Instructions

1. Read the bug description and the verified hint above.
2. Apply the minimal fix described; verify against the source files named in the hint.
3. Do NOT edit any test files - only fix source code.

The repository is at: {repo_path}

Important: Only modify source files (not test files)."""


def _format_oracle_recall(content: str, steps: list[str]) -> str:
    lines = [
        "- match_quality: oracle",
        "- similarity_score: 1.000",
        "- source: direct corpus injection (upper bound)",
        f"\n**Solution (verified accurate hint):**\n\n{content}",
    ]
    if steps:
        lines.append("\n**Steps:**")
        for i, step in enumerate(steps, 1):
            lines.append(f"{i}. {step}")
    return "\n".join(lines)


def _load_seed_by_id() -> dict[str, dict]:
    if not SEED_CORPUS.is_file():
        return {}
    return {e["instance_id"]: e for e in json.loads(SEED_CORPUS.read_text())}


def main() -> None:
    ap = argparse.ArgumentParser(description="Build per-cell prompts (control + good + oracle)")
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

    sys.path.insert(0, str(ROOT))
    from benchmark.agentbook_client import (  # noqa: WPS433
        AgentbookClient,
        build_search_query,
        format_recall_for_prompt,
    )

    seed_by_id = _load_seed_by_id()
    if not seed_by_id:
        raise SystemExit(
            f"Missing {SEED_CORPUS}. Run build_seed_corpus.py and seed_agentbook.py first."
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
    stack_errors: list[str] = []
    has_voyage_key = bool(os.environ.get("VOYAGE_API_KEY"))

    for entry in manifest:
        iid = entry["instance_id"]
        bug_text = (TASKS / iid / "BUG.md").read_text()
        seed_entry = seed_by_id.get(iid)
        if not seed_entry:
            raise SystemExit(f"No seed corpus entry for {iid}")

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
        emb = payload.get("embedding_provider")
        rerank = payload.get("rerank_provider")
        if has_voyage_key and emb == "fallback":
            stack_errors.append(f"{iid}: embedding_provider=fallback")
        if has_voyage_key and rerank == "noop":
            stack_errors.append(f"{iid}: rerank_provider=noop")

        top = (payload.get("results") or [{}])[0]
        recall_md = format_recall_for_prompt(payload)
        recall_payload = {
            **payload,
            "instance_id": iid,
            "query": query,
            "embedding_provider": emb,
            "rerank_provider": rerank,
        }
        (recalls_dir / f"{iid}.json").write_text(
            json.dumps(recall_payload, indent=2) + "\n"
        )

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
            "search_stack": {"embedding": emb, "rerank": rerank},
            "top_match_quality": top.get("match_quality"),
            "top_similarity_score": top.get("similarity_score"),
        }

        good_block = seed_entry["good"]
        oracle_recall = _format_oracle_recall(
            good_block["content"],
            good_block.get("steps") or [],
        )
        oracle_repo = str((RUNS / f"{iid}__oracle" / "repo").resolve())
        prompts[f"{iid}__oracle"] = {
            "instance_id": iid,
            "arm": "oracle",
            "prompt": ORACLE_PROMPT.format(
                bug_description=bug_text,
                agentbook_recall=oracle_recall,
                repo_path=oracle_repo,
            ),
            "repo_path": oracle_repo,
            "hint_source": "corpus.seed.json",
        }

    client.close()

    if stack_errors:
        print("search stack errors:", file=sys.stderr)
        for err in stack_errors[:10]:
            print(f"  {err}", file=sys.stderr)
        raise SystemExit(
            f"{len(stack_errors)} good-arm searches used fallback/noop with VOYAGE_API_KEY set"
        )

    args.output.write_text(json.dumps(prompts, indent=2) + "\n")
    n = len(manifest)
    stacks = sorted(
        {
            json.dumps(p.get("search_stack"), sort_keys=True)
            for p in prompts.values()
            if p.get("arm") == "good" and p.get("search_stack")
        }
    )
    print(f"Built {len(prompts)} prompts -> {args.output} (API RAG @ {args.api_url})")
    print(f"  control: {n}  good: {n}  oracle: {n}  recalls -> {recalls_dir}/")
    if stacks:
        print(f"  search stacks: {stacks}")


if __name__ == "__main__":
    main()
