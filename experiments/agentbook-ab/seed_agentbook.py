#!/usr/bin/env python
"""Seed good solutions into a running agentbook instance for the A/B good arm.

Uses corpus.simulated.json (run simulate_corpus.py first). Bad arm is not used.

Run:
  uv run python experiments/agentbook-ab/seed_agentbook.py
  uv run python experiments/agentbook-ab/seed_agentbook.py --base-url http://127.0.0.1:8078
  uv run python experiments/agentbook-ab/seed_agentbook.py --force
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from benchmark.agentbook_client import AgentbookClient  # noqa: E402
from benchmark.paths import CORPUS_SIMULATED, ORACLE  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed good corpus into agentbook API")
    ap.add_argument(
        "--base-url",
        default="http://127.0.0.1:8078",
        help="Agentbook API base URL",
    )
    ap.add_argument(
        "--corpus",
        type=Path,
        default=CORPUS_SIMULATED,
        help="Corpus JSON (default: _oracle/corpus.simulated.json)",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Re-register agent and re-seed (clears seed_state first)",
    )
    args = ap.parse_args()

    if not args.corpus.exists():
        raise SystemExit(
            f"corpus missing: {args.corpus}\n"
            "  uv run python experiments/agentbook-ab/simulate_corpus.py"
        )

    state_path = ORACLE / "seed_state_good.json"
    if args.force and state_path.exists():
        state_path.unlink()

    client = AgentbookClient(args.base_url)
    try:
        client.ping()
        print(f"agentbook API ok @ {args.base_url}")
        state = client.seed_good_corpus(
            args.corpus,
            skip_if_seeded=not args.force,
        )
        n_task = sum(1 for s in state.get("seeded", []) if "instance_id" in s)
        print(f"seeded {n_task} task problems + distractors -> {state_path}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
