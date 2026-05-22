#!/usr/bin/env python
"""Add missing hand corpus entries from gold.patch (do not overwrite existing).

Run:
  uv run python enrich_corpus.py --manifest tasks/manifest.json
  uv run python enrich_corpus.py --manifest tasks/manifest.multirepo.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from corpus_synth import (
    _func_from_patch,
    _narrate_change,
    _primary_file,
    extract_bug_fields,
    load_gold,
    load_hand_corpus,
    patched_files,
    synthesize_good,
)

ROOT = Path(__file__).parent
TASKS = ROOT / "tasks"
ORACLE = ROOT / "_oracle"
CORPUS_PATH = ORACLE / "corpus.json"


def _steps_from_patch(gold: str, primary: str, func: str) -> list[str]:
    steps = [
        f"Open {primary} and locate {func or 'the function named in the traceback'}",
        "Reproduce with the minimal example from the bug report",
    ]
    imports = [
        line[1:].strip()
        for line in gold.splitlines()
        if line.startswith("+from ") or line.startswith("+import ")
    ]
    if imports:
        steps.append(f"Add import(s) if missing: {imports[0][:80]}")
    if "try:" in gold and "except" in gold:
        exc = re.search(r"except (\w+)", gold)
        name = exc.group(1) if exc else "the expected exception"
        steps.append(f"Wrap the failing block in try/except {name} with a safe fallback")
    elif re.search(r"^[-+].*if ", gold, re.M):
        steps.append("Adjust the conditional branch so the correct code path runs for this input")
    else:
        steps.append("Apply the minimal source change described in the fix narrative")
    steps.append("Run the module's existing tests (do not edit test files)")
    return steps[:5]


def build_hand_entry(iid: str, bug_text: str) -> dict:
    gold = load_gold(iid)
    if not gold.strip():
        raise ValueError(f"no gold.patch for {iid}")
    description, error_signature, tags = extract_bug_fields(bug_text)
    syn = synthesize_good(iid, bug_text, gold)
    files = patched_files(gold)
    primary = _primary_file(gold, files)
    func = _func_from_patch(gold, primary)
    change = _narrate_change(gold)
    module = primary.replace("/", ".").replace(".py", "")
    func_bit = f", in `{func}()`" if func else ""

    content = (
        f"Root cause is in {module}{func_bit} ({primary}). "
        f"Symptom: {description[:200]}. "
        f"Fix: {change}. "
        f"Patched files: {', '.join(files[:4])}."
    )
    steps = _steps_from_patch(gold, primary, func)

    repo_tag = "sklearn" if iid.startswith("scikit-learn") else "sympy"
    if repo_tag not in tags:
        tags = [repo_tag, *tags]

    return {
        "instance_id": iid,
        "description": description,
        "error_signature": error_signature,
        "tags": tags[:8],
        "good": {"content": content, "steps": steps},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Enrich corpus.json from gold patches")
    ap.add_argument("--manifest", type=Path, default=TASKS / "manifest.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text())
    existing = load_hand_corpus()
    entries: list[dict] = []
    if CORPUS_PATH.is_file():
        entries = json.loads(CORPUS_PATH.read_text())

    by_id = {e["instance_id"]: e for e in entries}
    added = 0
    for entry in manifest:
        iid = entry["instance_id"]
        if iid in existing or iid in by_id:
            continue
        bug_text = (TASKS / iid / "BUG.md").read_text()
        hand = build_hand_entry(iid, bug_text)
        entries.append(hand)
        by_id[iid] = hand
        added += 1
        if args.dry_run:
            print(f"would add {iid}")

    if args.dry_run:
        print(f"would add {added} entries")
        return

    entries.sort(key=lambda e: e["instance_id"])
    CORPUS_PATH.write_text(json.dumps(entries, indent=2) + "\n")
    print(f"wrote {len(entries)} corpus entries -> {CORPUS_PATH} (+{added} new)")


if __name__ == "__main__":
    main()
