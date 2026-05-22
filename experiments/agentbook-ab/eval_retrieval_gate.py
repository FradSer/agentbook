#!/usr/bin/env python
"""Retrieval gate: verify good-arm RAG via production embed + rerank.

Runs GET /v1/search for every manifest task after seeding and asserts:
  - embedding_provider / rerank_provider match expectations (Voyage when keyed)
  - recall@1 and recall@3 on the task's ab_task:{instance_id} tag

Run (API must be up with VOYAGE_API_KEY + EMBEDDING_VERSION=v2):
  uv run python eval_retrieval_gate.py --manifest tasks/manifest.multirepo.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from benchmark.agentbook_client import (  # noqa: E402
    AgentbookClient,
    build_search_query,
)
from corpus_synth import (  # noqa: E402
    _primary_file,
    content_sufficient,
    load_gold,
    patched_files,
    steps_present,
)

TASKS = ROOT / "tasks"
DEFAULT_MANIFEST = TASKS / "manifest.json"
DEFAULT_OUT = ROOT / "retrieval_gate_report.json"
RECALLS = ROOT / "recalls"


def _recall_at_k(results: list[dict], tag: str, k: int) -> bool:
    for row in results[:k]:
        tags = row.get("tags") or []
        if tag in tags:
            return True
    return False


def _mrr(results: list[dict], tag: str) -> float:
    for i, row in enumerate(results, start=1):
        tags = row.get("tags") or []
        if tag in tags:
            return 1.0 / i
    return 0.0


def _expected_providers(
    client: AgentbookClient | None = None,
) -> tuple[str | None, str | None]:
    """Expected embed/rerank stack: probe live API first, then local env."""
    if client is not None:
        probe = client.search("sympy benchmark probe", limit=1)
        emb = probe.get("embedding_provider")
        rerank = probe.get("rerank_provider")
        if emb and emb != "fallback":
            return emb, rerank

    has_voyage = bool(os.environ.get("VOYAGE_API_KEY"))
    has_openrouter = bool(os.environ.get("OPENROUTER_API_KEY"))
    if has_voyage:
        return "voyage", "voyage"
    if has_openrouter:
        return "openrouter", "noop"
    return None, None


def _assert_stack(payload: dict, exp_emb: str | None, exp_rerank: str | None) -> str | None:
    emb = payload.get("embedding_provider")
    rerank = payload.get("rerank_provider")
    if exp_emb and emb != exp_emb:
        return f"embedding_provider={emb!r} expected {exp_emb!r}"
    if exp_rerank and rerank != exp_rerank:
        return f"rerank_provider={rerank!r} expected {exp_rerank!r}"
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description="Retrieval gate for good-arm RAG")
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--base-url", default="http://127.0.0.1:8078")
    ap.add_argument(
        "--search-limit",
        type=int,
        default=10,
        help="Top-k for recall@k metrics",
    )
    ap.add_argument("-o", "--output", type=Path, default=DEFAULT_OUT)
    ap.add_argument(
        "--allow-fallback",
        action="store_true",
        help="Do not require Voyage when keys are set (debug only)",
    )
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text())

    client = AgentbookClient(args.base_url)
    RECALLS.mkdir(exist_ok=True)
    per_task: list[dict] = []
    failures: list[str] = []
    by_repo: dict[str, list[dict]] = defaultdict(list)

    try:
        client.ping()
        client.ensure_agent()
        exp_emb, exp_rerank = _expected_providers(client)
        print(f"gate: {len(manifest)} tasks @ {args.base_url}")
        if exp_emb:
            print(f"expected stack: embedding={exp_emb} rerank={exp_rerank}")

        for entry in manifest:
            iid = entry["instance_id"]
            repo = entry.get("repo", "?")
            bug = (TASKS / iid / "BUG.md").read_text()
            query, err_log = build_search_query(bug)
            payload = client.search(query, error_log=err_log, limit=args.search_limit)
            tag = f"ab_task:{iid}"
            results = payload.get("results") or []

            recall_payload = {
                **payload,
                "instance_id": iid,
                "query": query,
                "expected_tag": tag,
            }
            (RECALLS / f"{iid}.json").write_text(
                json.dumps(recall_payload, indent=2) + "\n"
            )

            hit1 = _recall_at_k(results, tag, 1)
            hit3 = _recall_at_k(results, tag, 3)
            mrr = _mrr(results, tag)
            top = results[0] if results else {}
            best = top.get("best_solution") or {}
            content = best.get("content_preview") or ""
            steps = best.get("steps")
            if not steps_present(steps):
                solutions = top.get("solutions") or []
                if solutions:
                    steps = solutions[0].get("steps")
            gold = load_gold(iid)
            files = patched_files(gold)
            primary = _primary_file(gold, files) if files else ""
            content_ok = content_sufficient(
                content,
                primary_file=primary,
                match_quality=top.get("match_quality"),
            )
            steps_ok = steps_present(steps if isinstance(steps, list) else None)
            row = {
                "instance_id": iid,
                "repo": repo,
                "recall@1": hit1,
                "recall@3": hit3,
                "mrr": mrr,
                "content_sufficient@1": content_ok,
                "steps_present@1": steps_ok,
                "primary_file": primary,
                "embedding_provider": payload.get("embedding_provider"),
                "rerank_provider": payload.get("rerank_provider"),
                "top_tags": (results[0].get("tags") if results else []),
            }
            per_task.append(row)
            by_repo[repo].append(row)

            stack_err = None
            if not args.allow_fallback:
                stack_err = _assert_stack(payload, exp_emb, exp_rerank)
            if stack_err:
                failures.append(f"{iid}: {stack_err}")
            if not hit3:
                failures.append(
                    f"{iid}: recall@3 miss (top tags={row['top_tags']!r})"
                )
            if not content_ok:
                failures.append(
                    f"{iid}: content_sufficient@1 miss (primary={primary!r})"
                )
            if not steps_ok:
                failures.append(f"{iid}: steps_present@1 miss")

    finally:
        client.close()

    n = len(per_task)
    r1 = sum(1 for r in per_task if r["recall@1"]) / n if n else 0.0
    r3 = sum(1 for r in per_task if r["recall@3"]) / n if n else 0.0
    c1 = sum(1 for r in per_task if r["content_sufficient@1"]) / n if n else 0.0
    s1 = sum(1 for r in per_task if r["steps_present@1"]) / n if n else 0.0
    mean_mrr = sum(r["mrr"] for r in per_task) / n if n else 0.0

    report = {
        "manifest": str(args.manifest),
        "tasks": n,
        "recall@1": round(r1, 4),
        "recall@3": round(r3, 4),
        "content_sufficient@1": round(c1, 4),
        "steps_present@1": round(s1, 4),
        "mrr": round(mean_mrr, 4),
        "expected_embedding_provider": exp_emb,
        "expected_rerank_provider": exp_rerank,
        "failures": failures,
        "by_repo": {
            repo: {
                "tasks": len(rows),
                "recall@1": round(
                    sum(1 for r in rows if r["recall@1"]) / len(rows), 4
                ),
                "recall@3": round(
                    sum(1 for r in rows if r["recall@3"]) / len(rows), 4
                ),
            }
            for repo, rows in sorted(by_repo.items())
        },
        "per_task": per_task,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")

    print(
        f"recall@1={r1:.1%}  recall@3={r3:.1%}  "
        f"content@1={c1:.1%}  steps@1={s1:.1%}  mrr={mean_mrr:.3f}"
    )
    for repo, stats in sorted(report["by_repo"].items()):
        print(
            f"  {repo}: n={stats['tasks']} "
            f"R@1={stats['recall@1']:.1%} R@3={stats['recall@3']:.1%}"
        )
    print(f"report -> {args.output}")

    if failures:
        print(f"\nGATE FAILED ({len(failures)} issues):")
        for line in failures[:15]:
            print(f"  {line}")
        if len(failures) > 15:
            print(f"  ... +{len(failures) - 15} more")
        raise SystemExit(1)

    print("\nGATE PASSED")


if __name__ == "__main__":
    main()
