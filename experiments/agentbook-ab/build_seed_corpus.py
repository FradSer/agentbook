#!/usr/bin/env python
"""Build corpus for agentbook API seeding (good arm only).

Prefers hand-authored entries from ``_oracle/corpus.json``; otherwise builds
good solutions from ``gold.patch`` with an excerpt so RAG matches the real fix.

Output is written to ``_oracle/corpus.seed.json`` and consumed by
``seed_agentbook.py`` (POST /v1/problems + /solutions) before any good-arm run.

Run:
  uv run python experiments/agentbook-ab/build_seed_corpus.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from corpus_synth import (
    extract_bug_fields,
    load_gold,
    load_hand_corpus,
    patched_files,
    synthesize_good,
)

ROOT = Path(__file__).parent
TASKS = ROOT / "tasks"
ORACLE = ROOT / "_oracle"
DEFAULT_MANIFEST = TASKS / "manifest.json"
DEFAULT_OUT = ORACLE / "corpus.seed.json"


def _gold_excerpt(gold: str, *, max_lines: int = 40) -> str:
    lines = [
        line
        for line in gold.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    if not lines:
        return ""
    body = "\n".join(lines[:max_lines])
    if len(lines) > max_lines:
        body += f"\n... ({len(lines) - max_lines} more added lines)"
    return body


def build_entry(iid: str, bug_text: str, hand: dict | None) -> dict:
    description, error_signature, tags = extract_bug_fields(bug_text)
    if hand:
        good = dict(hand["good"])
        content = good["content"]
    else:
        gold = load_gold(iid)
        syn = synthesize_good(iid, bug_text, gold)
        content = syn["content"]
        good = {"content": content, "steps": syn["steps"]}
        excerpt = _gold_excerpt(gold)
        if excerpt:
            files = patched_files(gold)
            primary = files[0] if files else "sympy"
            content = (
                f"{content}\n\n"
                f"**Verified fix locations:** {', '.join(files[:4])}\n\n"
                f"**Key patch hunks (from the resolved change):**\n```diff\n{excerpt}\n```"
            )
            good["content"] = content

    return {
        "instance_id": iid,
        "description": description,
        "error_signature": error_signature,
        "tags": tags,
        "good": good,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Build corpus.seed.json for API seeding")
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("-o", "--output", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text())
    hand_all = load_hand_corpus()
    corpus: list[dict] = []
    hand_kept = 0
    from_gold = 0

    for entry in manifest:
        iid = entry["instance_id"]
        bug_text = (TASKS / iid / "BUG.md").read_text()
        hand = hand_all.get(iid)
        if hand:
            hand_kept += 1
        else:
            from_gold += 1
        corpus.append(build_entry(iid, bug_text, hand))

    args.output.write_text(json.dumps(corpus, indent=2) + "\n")
    print(f"wrote {len(corpus)} seed entries -> {args.output}")
    print(f"  hand: {hand_kept}  gold-backed: {from_gold}")


if __name__ == "__main__":
    main()
