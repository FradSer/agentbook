#!/usr/bin/env python
"""Verify good-arm data was written via agentbook API before running agents.

Checks seed_state_good.json and spot-checks GET /v1/search for each manifest task.

Run after seed_agentbook.py:
  uv run python experiments/agentbook-ab/verify_agentbook_seed.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from benchmark.agentbook_client import (  # noqa: E402
    AgentbookClient,
    build_search_query,
)
from benchmark.paths import DEFAULT_MANIFEST, ORACLE  # noqa: E402

SEED_STATE = ORACLE / "seed_state_good.json"
TASKS = ROOT / "tasks"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--base-url", default="http://127.0.0.1:8078")
    ap.add_argument(
        "--require-search-hit",
        action="store_true",
        default=True,
        help="Each task must return its ab_task tag in top search result",
    )
    ap.add_argument(
        "--require-server-embeddings",
        action="store_true",
        default=True,
        help="Fail if search uses fallback embedding while VOYAGE/OPENROUTER keys exist",
    )
    args = ap.parse_args()

    if not SEED_STATE.exists():
        raise SystemExit(
            f"missing {SEED_STATE.name}; run seed_agentbook.py first"
        )

    manifest = json.loads(args.manifest.read_text())
    expected = {e["instance_id"] for e in manifest}
    state = json.loads(SEED_STATE.read_text())
    seeded_rows = [
        s for s in state.get("seeded", []) if "instance_id" in s
    ]
    seeded_ids = {s["instance_id"] for s in seeded_rows}

    missing = sorted(expected - seeded_ids)
    if missing:
        raise SystemExit(
            f"seed incomplete: {len(seeded_ids)}/{len(expected)} tasks; "
            f"missing {missing[:5]}{'...' if len(missing) > 5 else ''}"
        )

    client = AgentbookClient(args.base_url)
    try:
        client.ping()
        client.ensure_agent()
        print(f"agentbook ok @ {args.base_url}")
        print(f"seed_state: {len(seeded_ids)} task problems registered")

        if args.require_server_embeddings:
            probe = client.search("sympy benchmark probe", limit=1)
            emb = probe.get("embedding_provider")
            rerank = probe.get("rerank_provider")
            print(f"search stack: embedding={emb} rerank={rerank}")
            import os

            has_key = bool(
                os.environ.get("VOYAGE_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
            )
            if has_key and emb == "fallback":
                raise SystemExit(
                    "search uses embedding_provider=fallback but VOYAGE_API_KEY or "
                    "OPENROUTER_API_KEY is set — restart API with resolve_search_stack "
                    "(DEMO_MODE must not force FallbackEmbeddingProvider)"
                )

        if not args.require_search_hit:
            return

        bad: list[str] = []
        for iid in sorted(expected):
            bug = (TASKS / iid / "BUG.md").read_text()
            query, err_log = build_search_query(bug)
            payload = client.search(query, error_log=err_log, limit=3)
            tag = f"ab_task:{iid}"
            results = payload.get("results") or []
            if not results:
                bad.append(f"{iid}: no search results")
                continue
            top = results[0]
            tags = top.get("tags") or []
            if tag not in tags:
                bad.append(
                    f"{iid}: top hit tags={tags!r} "
                    f"quality={top.get('match_quality')}"
                )
        if bad:
            raise SystemExit(
                "search verification failed:\n  "
                + "\n  ".join(bad[:10])
                + (f"\n  ... +{len(bad) - 10} more" if len(bad) > 10 else "")
            )
        print(f"search spot-check: {len(expected)}/{len(expected)} tasks hit ab_task tag")
    finally:
        client.close()

    print("seed verification passed — safe to build prompts and run good arm")


if __name__ == "__main__":
    main()
