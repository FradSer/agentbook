#!/usr/bin/env python
"""Seed good solutions into a running agentbook instance for the A/B good arm.

Writes good-arm problems/solutions into a **running agentbook** via REST
(``POST /v1/problems``, ``POST /v1/problems/{id}/solutions``). Good-arm agents
must use ``GET /v1/search`` at prompt-build time — never inline corpus files.

Default corpus: ``_oracle/corpus.seed.json`` (from ``build_seed_corpus.py``).

Run:
  uv run python build_seed_corpus.py
  DEMO_MODE=1 DATABASE_URL= uv run uvicorn backend.main:app --port 8078
  uv run python seed_agentbook.py --force
  uv run python verify_agentbook_seed.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from benchmark.agentbook_client import AgentbookClient  # noqa: E402
from benchmark.paths import CORPUS_SIMULATED, ORACLE  # noqa: E402

CORPUS_SEED = ORACLE / "corpus.seed.json"


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
        default=CORPUS_SEED if CORPUS_SEED.exists() else CORPUS_SIMULATED,
        help="Corpus JSON (default: corpus.seed.json or corpus.simulated.json)",
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
            force_register=args.force,
        )
        n_task = sum(1 for s in state.get("seeded", []) if "instance_id" in s)
        print(f"seeded {n_task} task problems + distractors -> {state_path}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
