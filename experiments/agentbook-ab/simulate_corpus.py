#!/usr/bin/env python
"""Build a realistic simulated agentbook corpus, then validate recall@1.

Writes ``_oracle/corpus.simulated.json`` — symptom text from BUG.md, solution
text structured like hand-authored corpus entries (not raw gold-line dumps).
Hand entries in ``corpus.json`` are kept when ``--prefer-hand`` (default).

Run:
  uv run python experiments/agentbook-ab/simulate_corpus.py
  uv run python experiments/agentbook-ab/simulate_corpus.py --manifest tasks/manifest.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from corpus_synth import load_hand_corpus, simulate_recall_at_1, synthesize_entry

ROOT = Path(__file__).parent
TASKS = ROOT / "tasks"
ORACLE = ROOT / "_oracle"
DEFAULT_MANIFEST = TASKS / "manifest.json"
DEFAULT_OUT = ORACLE / "corpus.simulated.json"
RECALL_REPORT = ROOT / "recall_simulation.json"


def main() -> None:
    ap = argparse.ArgumentParser(description="Simulate realistic agentbook corpus")
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("-o", "--output", type=Path, default=DEFAULT_OUT)
    ap.add_argument(
        "--prefer-hand",
        action="store_true",
        default=True,
        help="Keep hand-authored good/bad from corpus.json when present",
    )
    ap.add_argument(
        "--no-prefer-hand",
        action="store_false",
        dest="prefer_hand",
        help="Synthesize every task from gold.patch",
    )
    ap.add_argument("--recall-report", type=Path, default=RECALL_REPORT)
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text())
    hand = load_hand_corpus() if args.prefer_hand else {}
    corpus: list[dict] = []
    hand_kept = 0
    synthesized = 0

    for entry in manifest:
        iid = entry["instance_id"]
        bug_path = TASKS / iid / "BUG.md"
        bug_text = bug_path.read_text()
        prefer = hand.get(iid)
        if prefer:
            hand_kept += 1
        else:
            synthesized += 1
        corpus.append(
            synthesize_entry(iid, bug_text, prefer_hand=prefer if args.prefer_hand else None)
        )

    args.output.write_text(json.dumps(corpus, indent=2) + "\n")
    print(f"wrote {len(corpus)} entries -> {args.output}")
    print(f"  hand-kept: {hand_kept}  synthesized: {synthesized}")

    report = simulate_recall_at_1(corpus)
    args.recall_report.write_text(json.dumps(report, indent=2) + "\n")
    print(
        f"recall@1 (lexical proxy): {report['hit_at_1']}/{report['total']} "
        f"({100 * report['hit_rate']:.1f}%) -> {args.recall_report.name}"
    )
    misses = [r for r in report["per_task"] if not r["recall_at_1"]]
    if misses:
        print(f"  misses ({len(misses)}):")
        for r in misses[:8]:
            print(f"    {r['instance_id']:28s} top={r['top_match']}")
        if len(misses) > 8:
            print(f"    ... +{len(misses) - 8} more")


if __name__ == "__main__":
    main()
