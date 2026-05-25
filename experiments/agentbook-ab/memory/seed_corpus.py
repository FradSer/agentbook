#!/usr/bin/env python
"""Assemble the corpora the rebuilt eval serves:

  _oracle/memories.json  -- GOOD arm: leakage-free peer-agent memories, only for
                            tasks the strong solver genuinely solved.
  _oracle/oracle.json    -- ORACLE arm: gold-derived upper bound (clearly labeled
                            ceiling; may contain the fix location/excerpt).

`--seed-live` seeds memories.json (+ sympy distractors) into the running
agentbook API and records the problem_id -> instance_id map.

Usage:
  uv run python -m memory.seed_corpus
  uv run python -m memory.seed_corpus --seed-live --base http://127.0.0.1:8078
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from benchmark.bugfields import extract_bug_fields  # noqa: E402
from benchmark.paths import DEFAULT_MANIFEST, ORACLE, TASKS  # noqa: E402

from memory.to_memory_entry import build_entry  # noqa: E402

MEMORIES_OUT = ORACLE / "memories.json"
ORACLE_OUT = ORACLE / "oracle.json"
VERIFIED = ORACLE / "solver_verified.json"


def _gold_excerpt(iid: str, max_lines: int = 40) -> tuple[list[str], list[str]]:
    """Return (changed_files, added_code_lines) from the held-out gold.patch."""
    patch = (ORACLE / iid / "gold.patch").read_text(errors="replace")
    files: list[str] = []
    added: list[str] = []
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            files.append(line[6:].strip())
        elif line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
    return files, added[:max_lines]


def build_memories(manifest_path: Path) -> list[dict]:
    if not VERIFIED.exists():
        sys.exit(f"missing {VERIFIED}; run memory.verify_solution first")
    verified = {
        r["instance_id"]: r
        for r in json.loads(VERIFIED.read_text())
        if r.get("resolved")
    }
    manifest = json.loads(manifest_path.read_text())
    entries: list[dict] = []
    for e in manifest:
        iid = e["instance_id"]
        if iid not in verified:
            continue
        entries.append(build_entry(iid))
    return entries


def build_oracle(manifest_path: Path) -> list[dict]:
    manifest = json.loads(manifest_path.read_text())
    entries: list[dict] = []
    for e in manifest:
        iid = e["instance_id"]
        bug = (TASKS / iid / "BUG.md").read_text()
        description, error_signature, tags = extract_bug_fields(bug)
        files, added = _gold_excerpt(iid)
        diff_block = "\n".join(added)
        content = (
            f"Verified gold fix lives in: {', '.join(files) or 'see steps'}.\n\n"
            f"Key additions from the resolved change:\n```diff\n{diff_block}\n```"
        )
        entries.append(
            {
                "instance_id": iid,
                "description": description,
                "error_signature": error_signature,
                "tags": tags,
                "content": content,
                "steps": [
                    f"Open {files[0] if files else 'the affected module'}",
                    "Apply the additions shown above; adjust to local source.",
                ],
                "source": "gold (oracle ceiling -- not a realistic memory)",
            }
        )
    return entries


def main() -> None:
    ap = argparse.ArgumentParser(description="Assemble + optionally seed corpora")
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--seed-live", action="store_true", help="seed memories into API")
    ap.add_argument("--base", default="http://127.0.0.1:8078")
    ap.add_argument(
        "--no-distractors", action="store_true", help="skip sympy distractors"
    )
    args = ap.parse_args()

    memories = build_memories(args.manifest)
    MEMORIES_OUT.write_text(json.dumps(memories, indent=2) + "\n")
    leaks = sum(m["leak_lines_removed"] for m in memories)
    print(
        f"good memories: {len(memories)} (leak lines scrubbed: {leaks}) -> "
        f"{MEMORIES_OUT}"
    )

    oracle = build_oracle(args.manifest)
    ORACLE_OUT.write_text(json.dumps(oracle, indent=2) + "\n")
    print(f"oracle ceiling: {len(oracle)} -> {ORACLE_OUT}")

    if args.seed_live:
        from benchmark.agentbook_client import AgentbookClient

        client = AgentbookClient(base_url=args.base)
        state = client.seed_memories(
            MEMORIES_OUT, include_distractors=not args.no_distractors
        )
        client.close()
        print(
            f"seeded {len(state.get('memories_seeded', []))} memories + "
            f"{len(state.get('distractor_pids', []))} distractors into {args.base}"
        )


if __name__ == "__main__":
    main()
