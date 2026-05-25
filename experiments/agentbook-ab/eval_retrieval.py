#!/usr/bin/env python
"""Layer 1 -- honest retrieval evaluation (replaces eval_retrieval_gate.py).

The old gate tagged every memory with a unique `ab_task:{id}` and "measured"
recall by checking for that tag, so recall was structurally 100% regardless of
embedding quality. This version:

  - seeds leakage-free `good` memories + same-domain sympy distractors (no unique
    per-task tag);
  - queries GET /v1/search with the BUG.md description only (what a control agent
    would form);
  - measures recall@k by the retrieved problem_id IDENTITY, plus whether the
    correct memory ranks above EVERY distractor, MRR, and no_good_match calibration.

100% is no longer forced; the headline is the measured number.

Usage:
  uv run python eval_retrieval.py --base http://127.0.0.1:8078
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from benchmark.agentbook_client import AgentbookClient  # noqa: E402
from benchmark.agentbook_client import (  # noqa: E402
    format_recall_for_prompt as format_recall_for_prompt,
)
from benchmark.bugfields import build_query  # noqa: E402
from benchmark.paths import ORACLE, TASKS  # noqa: E402

REPORT_OUT = ROOT / "retrieval_report.json"
RECALL_CACHE = ORACLE / "recall_cache.json"
MEMORIES = ORACLE / "memories.json"


def evaluate(base: str, limit: int, reseed: bool) -> dict:
    client = AgentbookClient(base_url=base)
    if reseed:
        state = client.seed_memories(MEMORIES, include_distractors=True)
    else:
        state = client._load_state()  # reuse the last seed
    pid_to_iid: dict[str, str] = state.get("pid_to_iid", {})
    distractor_pids = set(state.get("distractor_pids", []))
    if not pid_to_iid:
        client.close()
        sys.exit("no seeded memories found; run with reseed or seed_corpus --seed-live")
    iid_to_pid = {v: k for k, v in pid_to_iid.items()}

    per_task: list[dict] = []
    cache: dict[str, dict] = {}
    for iid in sorted(iid_to_pid):
        correct_pid = iid_to_pid[iid]
        bug = (TASKS / iid / "BUG.md").read_text()
        query, err_log = build_query(bug)
        payload = client.search(query, error_log=err_log, limit=limit)
        results = payload.get("results") or []
        # cache the formatted hint per task so the (parallel) good arm reads it
        # offline -- one search per task, not one per cell -- bypassing the
        # Voyage 3 RPM free-tier limit during the big run.
        top = results[0] if results else {}
        cache[iid] = {
            "recall": format_recall_for_prompt(payload),
            "meta": {
                "hint": "good",
                "query": query,
                "top_problem_id": top.get("problem_id"),
                "top_similarity": top.get("similarity_score"),
                "no_good_match": payload.get("no_good_match"),
                "results_count": len(results),
            },
        }
        order = [r.get("problem_id") for r in results]
        rank = order.index(correct_pid) + 1 if correct_pid in order else 0
        # best (smallest) rank held by any distractor
        distractor_ranks = [
            i + 1 for i, pid in enumerate(order) if pid in distractor_pids
        ]
        top_distractor = min(distractor_ranks) if distractor_ranks else None
        wins = bool(rank and (top_distractor is None or rank < top_distractor))
        per_task.append(
            {
                "instance_id": iid,
                "rank": rank,
                "recall@1": bool(rank == 1),
                "recall@3": bool(0 < rank <= 3),
                "recall@5": bool(0 < rank <= 5),
                "mrr": (1.0 / rank) if rank else 0.0,
                "wins_above_distractors": wins,
                "top_distractor_rank": top_distractor,
                "top_similarity": (
                    results[0].get("similarity_score") if results else None
                ),
                "top_match_quality": (
                    results[0].get("match_quality") if results else None
                ),
                "no_good_match": payload.get("no_good_match"),
                "embedding_provider": payload.get("embedding_provider"),
                "rerank_provider": payload.get("rerank_provider"),
            }
        )
    client.close()
    RECALL_CACHE.write_text(json.dumps(cache, indent=2) + "\n")

    n = len(per_task)
    agg = {
        "base": base,
        "tasks": n,
        "distractors_seeded": len(distractor_pids),
        "recall@1": round(sum(t["recall@1"] for t in per_task) / n, 4) if n else 0,
        "recall@3": round(sum(t["recall@3"] for t in per_task) / n, 4) if n else 0,
        "recall@5": round(sum(t["recall@5"] for t in per_task) / n, 4) if n else 0,
        "mrr": round(sum(t["mrr"] for t in per_task) / n, 4) if n else 0,
        "wins_above_distractors": round(
            sum(t["wins_above_distractors"] for t in per_task) / n, 4
        )
        if n
        else 0,
        "embedding_provider": per_task[0]["embedding_provider"] if per_task else None,
        "rerank_provider": per_task[0]["rerank_provider"] if per_task else None,
        "per_task": per_task,
    }
    return agg


def main() -> None:
    ap = argparse.ArgumentParser(description="Layer 1 honest retrieval eval")
    ap.add_argument("--base", default="http://127.0.0.1:8078")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument(
        "--no-reseed",
        action="store_true",
        help="reuse the existing seed instead of re-seeding memories",
    )
    args = ap.parse_args()

    report = evaluate(args.base, args.limit, reseed=not args.no_reseed)
    REPORT_OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(
        f"tasks={report['tasks']} recall@1={report['recall@1']} "
        f"recall@3={report['recall@3']} mrr={report['mrr']} "
        f"wins_above_distractors={report['wins_above_distractors']} "
        f"(embed={report['embedding_provider']}, rerank={report['rerank_provider']})"
    )
    print(f"-> {REPORT_OUT}")


if __name__ == "__main__":
    main()
