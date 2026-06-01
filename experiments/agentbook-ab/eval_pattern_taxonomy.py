#!/usr/bin/env python
"""Validate the discrete root-cause taxonomy at scale before building it.

Dead end (04_cross_task_retrieval.md): dense retrieval can't rank a sibling above
same-library noise. Proposed fix: tag memories with a discrete root-cause CLASS
and retrieve by tag. Non-obvious risk: at search time we only have an unsolved
bug, so the class must be predictable from symptoms alone.

Two INDEPENDENT claude -p passes (subscription creds, no Voyage/OpenRouter quota),
over the FULL corpus (corpus.json `good` = solution prose, 56 tasks, no reliance
on the noisy hand-labelled sib_pairs):
  A. induce a taxonomy from the solved solutions + label each memory's class.
  B. given ONLY that fixed taxonomy + the raw BUG.md (no fix), predict each task's
     class.
Headline = query-class accuracy: pred(BUG_t) == mem_class(solution_t). Two
same-class memories are mutually tag-retrievable iff this prediction is reliable,
so accuracy at n=56 is the operational signal. Also report class-size
discrimination (a tag that lumps everything together is useless).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent
ORACLE = ROOT / "_oracle"
TASKS = ROOT / "tasks"
CLAUDE = Path(os.path.expanduser("~/.local/bin/claude"))

_PROVIDER_ENV = (
    "CLAUDE_CODE_OAUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
)
_JSON_RE = re.compile(r"```json\s*\n(.*?)```", re.DOTALL)


def _env() -> dict:
    e = dict(os.environ)
    for k in _PROVIDER_ENV:
        e.pop(k, None)
    return e


def _claude(prompt: str, model: str = "opus", timeout: int = 600) -> dict:
    cmd = [
        str(CLAUDE),
        "-p",
        prompt,
        "--output-format",
        "json",
        "--no-session-persistence",
        "--model",
        model,
        "--disallowedTools",
        "WebSearch",
        "WebFetch",
        "Bash",
        "Read",
        "Edit",
        "Write",
    ]
    with tempfile.TemporaryDirectory(prefix="ab-tax-") as cwd:
        r = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=_env()
        )
    text = json.loads(r.stdout).get("result") or ""
    m = _JSON_RE.search(text)
    blob = m.group(1) if m else text[text.find("{") : text.rfind("}") + 1]
    return json.loads(blob)


def main() -> None:
    corpus = json.load(open(ORACLE / "corpus.json"))
    items = [e for e in corpus if (TASKS / e["instance_id"] / "BUG.md").exists()]
    ids = [e["instance_id"] for e in items]
    good = {e["instance_id"]: e["good"] for e in items}

    def mem_text(iid: str) -> str:
        g = good[iid]
        steps = " ".join(g.get("steps") or [])
        return (g.get("content", "") + " " + steps)[:700]

    # --- Pass A: induce taxonomy + label each memory by ROOT CAUSE ---
    blocks = "\n".join(f"[{iid}] {mem_text(iid)}" for iid in ids)
    prompt_a = (
        "You are designing a retrieval taxonomy for a bug-fix memory layer. Below "
        "are solved Python bugs (root cause + fix), each prefixed with an id.\n\n"
        + blocks
        + "\n\nInduce a COMPACT taxonomy of root-cause CLASSES (aim for "
        "8-14 classes; each a short kebab-case slug + one-line description) so that "
        "bugs sharing an abstract failure mode get the same class and unrelated "
        "bugs do not. Assign each id EXACTLY ONE class slug. Output ONLY a ```json "
        'block: {"taxonomy":[{"slug":...,"desc":...}],"assignments":{"<id>":"<slug>"}}'
    )
    print(f"pass A: taxonomy + labels over {len(ids)} memories...", flush=True)
    a = _claude(prompt_a)
    taxonomy = a["taxonomy"]
    mem_class = a["assignments"]

    # --- Pass B: predict class from raw BUG only, against the FIXED taxonomy ---
    tax_str = "\n".join(f"- {t['slug']}: {t['desc']}" for t in taxonomy)
    bugs = "\n\n".join(
        f"[{iid}]\n{(TASKS / iid / 'BUG.md').read_text()[:800]}" for iid in ids
    )
    prompt_b = (
        "Here is a fixed taxonomy of bug root-cause classes:\n\n"
        + tax_str
        + "\n\nBelow are bug reports (symptoms only, NO fix). For each id, predict "
        "the single most likely root-cause class slug from the taxonomy above "
        "(use 'unknown' if none fits). Reason from symptoms alone.\n\n"
        + bugs
        + '\n\nOutput ONLY a ```json block: {"predictions":{"<id>":"<slug>"}}'
    )
    print(f"pass B: predict class from BUG for {len(ids)} tasks...", flush=True)
    b = _claude(prompt_b)
    pred = b["predictions"]

    # --- Score ---
    sizes = Counter(mem_class.get(i) for i in ids)
    correct = [i for i in ids if pred.get(i) == mem_class.get(i)]
    acc = round(len(correct) / len(ids), 3)
    # operational: task can tag-retrieve >=1 OTHER same-class memory
    retrievable = [i for i in correct if sizes.get(mem_class.get(i), 0) >= 2]
    eff = round(len(retrievable) / len(ids), 3)

    report = {
        "n_tasks": len(ids),
        "n_classes": len(taxonomy),
        "largest_class_frac": round(max(sizes.values()) / len(ids), 3),
        "singleton_classes": sum(1 for c, n in sizes.items() if n == 1),
        "query_class_accuracy": acc,
        "effective_tag_retrievable": eff,
        "taxonomy": taxonomy,
        "memory_classes": mem_class,
        "query_predictions": pred,
        "class_sizes": dict(sizes),
    }
    (ORACLE / "pattern_taxonomy_report.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        f"\n== {len(ids)} tasks, {len(taxonomy)} classes, "
        f"largest={report['largest_class_frac']:.0%}, "
        f"singletons={report['singleton_classes']} =="
    )
    print(f"query-class accuracy   = {acc}  (symptom->class recovers memory class)")
    print(f"effective tag-retrieval = {eff}  (correct AND class has a sibling)")
    print("\nclass sizes:", dict(sizes))


if __name__ == "__main__":
    main()
