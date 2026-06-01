#!/usr/bin/env python
"""Held-out sibling recall: the cross-task-transfer precursor to the LOO fix run.

Same-task recall is already 1.0 (each task is seeded with its own memory). The
open question is whether a task's query surfaces a *sibling* task's memory when
its own memory is absent -- i.e. whether retrieval can carry transferable
knowledge at all. We approximate the hold-out cheaply: seed every leak-free
memory once, query each sibling task, drop the self-hit from the ranking, and
measure where the sibling lands in the remainder.

Run (API up on 8079 with the Voyage v2 stack + seeded):
  uv run python eval_sibling_recall.py --base-url http://127.0.0.1:8079
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from benchmark.agentbook_client import AgentbookClient, build_search_query  # noqa: E402

ORACLE = ROOT / "_oracle"
TASKS = ROOT / "tasks"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8079")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--reseed", action="store_true")
    ap.add_argument(
        "-o", "--output", default=str(ORACLE / "sibling_recall_report.json")
    )
    args = ap.parse_args()

    sib_pairs = json.loads((ORACLE / "sib_pairs.json").read_text())
    client = AgentbookClient(args.base_url)
    client.ping()

    state = client._load_state()
    if args.reseed or state.get("mode") != "memories" or not state.get("pid_to_iid"):
        print("seeding leak-free memories.json (+distractors)...")
        state = client.seed_memories(ORACLE / "memories.json", include_distractors=True)
    pid_to_iid = state["pid_to_iid"]
    print(f"seeded {len(pid_to_iid)} memories")

    per_task = []
    for iid, sibling in sib_pairs.items():
        if not sibling:
            continue
        bug = (TASKS / iid / "BUG.md").read_text()
        query, err_log = build_search_query(bug)
        payload = client.search(query, error_log=err_log, limit=args.limit)
        results = payload.get("results") or []
        ranked_iids = [pid_to_iid.get(r.get("problem_id")) for r in results]
        scored = [
            (
                pid_to_iid.get(r.get("problem_id")),
                round(r.get("similarity_score", 0), 3),
            )
            for r in results
        ]
        sib_score = next((s for i, s in scored if i == sibling), None)
        # Hold-out proxy: remove the self memory, re-rank the remainder.
        held_out = [x for x in ranked_iids if x != iid]
        sib_rank = (held_out.index(sibling) + 1) if sibling in held_out else None
        per_task.append(
            {
                "instance_id": iid,
                "sibling": sibling,
                "sibling_rank_holdout": sib_rank,
                "self_was_top": ranked_iids[:1] == [iid],
                "n_results": len(results),
                "sibling_score": sib_score,
                "embedding_provider": payload.get("embedding_provider"),
                "scored": scored[:8],
            }
        )

    n = len(per_task)

    def at(k: int) -> float:
        hits = sum(
            1
            for r in per_task
            if r["sibling_rank_holdout"] and r["sibling_rank_holdout"] <= k
        )
        return round(hits / n, 3) if n else 0.0

    mrr = (
        round(
            sum(
                1.0 / r["sibling_rank_holdout"]
                for r in per_task
                if r["sibling_rank_holdout"]
            )
            / n,
            3,
        )
        if n
        else 0.0
    )

    report = {
        "tasks_with_sibling": n,
        "embedding_provider": per_task[0]["embedding_provider"] if per_task else None,
        "sibling_recall@1": at(1),
        "sibling_recall@3": at(3),
        "sibling_recall@5": at(5),
        "sibling_mrr_holdout": mrr,
        "per_task": per_task,
    }
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    client.close()

    print(
        f"\n== held-out sibling recall ({n} tasks, {report['embedding_provider']}) =="
    )
    print(
        f"recall@1={report['sibling_recall@1']}  recall@3={report['sibling_recall@3']}  "
        f"recall@5={report['sibling_recall@5']}  mrr={report['sibling_mrr_holdout']}"
    )
    for r in per_task:
        print(
            f"  {r['instance_id']} -> {r['sibling']}: rank={r['sibling_rank_holdout']} "
            f"(n={r['n_results']}, self_top={r['self_was_top']})"
        )
    print(f"\nreport -> {args.output}")


if __name__ == "__main__":
    main()
