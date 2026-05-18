"""Synthesize agentbook-shaped corpus entries from BUG.md + gold.patch.

Produces symptom text an agent would have written *before* seeing tests,
and solution text *after* a successful fix — without dumping raw diff lines.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

ORACLE = Path(__file__).parent / "_oracle"

_EXCEPTION_RE = re.compile(
    r"([A-Z][A-Za-z0-9_]*(?:Error|Exception))(?:\s*:\s*([^\n.]{5,120}))?"
)
_SKIP_SECTIONS = frozenset(
    {
        "environment",
        "patch info",
        "reproduction script",
        "traceback",
    }
)


def patched_files(patch: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r"^\+\+\+ b/(.+)$", patch, re.M)]


def load_gold(iid: str) -> str:
    path = ORACLE / iid / "gold.patch"
    return path.read_text() if path.exists() else ""


def extract_bug_fields(bug_text: str) -> tuple[str, str, list[str]]:
    """Return (description, error_signature, tags)."""
    lines = bug_text.splitlines()
    body: list[str] = []
    in_code = False
    for line in lines[2:]:
        low = line.strip().lower()
        if low.startswith("## ") and any(s in low for s in _SKIP_SECTIONS):
            break
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if line.strip().startswith("---"):
            break
        if line.strip():
            body.append(line.strip())

    description = re.sub(r"\s+", " ", " ".join(body))[:420]
    if not description:
        description = lines[2].strip()[:420] if len(lines) > 2 else bug_text[:200]

    err = ""
    for m in _EXCEPTION_RE.finditer(bug_text):
        msg = (m.group(2) or "").strip()
        err = f"{m.group(1)}: {msg}" if msg else m.group(1)
    if not err:
        for line in bug_text.splitlines():
            if "Error" in line or "Exception" in line:
                err = line.strip()[:120]
                break
    if not err:
        err = description[:80]

    tags = ["sympy"]
    for kw in (
        "subs",
        "Piecewise",
        "Mod",
        "imageset",
        "intersect",
        "printer",
        "latex",
        "assumption",
        "Matrix",
        "solve",
        "integrate",
        "diff",
        "codegen",
        "parse",
    ):
        if kw.lower() in bug_text.lower():
            tags.append(kw)
    return description, err, tags[:8]


def _primary_file(patch: str, files: list[str]) -> str:
    if not files:
        return "sympy/core/basic.py"
    scores: dict[str, int] = {f: 0 for f in files}
    for line in patch.splitlines():
        if not (line.startswith("+") or line.startswith("-")) or line.startswith("+++") or line.startswith("---"):
            continue
        for f in files:
            if f in line:
                scores[f] += 1
    return max(scores, key=scores.get)


def _func_from_patch(patch: str, primary: str) -> str:
    for line in patch.splitlines():
        if line.startswith("@@") and primary.replace("/", "/") in line:
            m = re.search(r"def (\w+)", line)
            if m:
                return m.group(1)
    for line in patch.splitlines():
        if line.startswith("@@") and "def " in line:
            m = re.search(r"def (\w+)", line)
            if m:
                return m.group(1)
    return ""


def _narrate_change(patch: str) -> str:
    text = patch.lower()
    if "try:" in patch and "except" in patch:
        exc = re.search(r"except (\w+)", patch)
        name = exc.group(1) if exc else "the expected exception"
        return (
            f"wrap the failing block in try/except {name} and use a safe fallback "
            f"so evaluation continues instead of propagating the error"
        )
    if "isinstance(" in patch and "+        if isinstance" not in patch:
        return "widen an isinstance guard so nested types (e.g. Pow inside Mul) are parenthesised correctly"
    if "return none" in text or "return None" in patch:
        return "return None from the assumption helper when the predicate cannot be decided, instead of running a fragile test"
    if "from sympy" in patch and patch.count("+++") <= 3:
        return "add the missing import and thread it through the handler that raises at runtime"
    if re.search(r"^\+.*\)$", patch, re.M) and "return" in patch:
        return "adjust the return expression so the constructed object matches the mathematical definition"
    if "-        if " in patch and "+        if " in patch:
        return "fix the conditional branch so the correct code path runs for this input shape"
    adds = [
        line[1:].strip()
        for line in patch.splitlines()
        if line.startswith("+") and not line.startswith("+++") and line.strip()
    ]
    if adds:
        sample = adds[0][:100]
        return f"apply a minimal change along the lines of `{sample}` (see the patched module)"
    return "apply the minimal source change in the patched module"


_WRONG_SIBLING: dict[str, str] = {
    "mod.py": "mul.py",
    "add.py": "mul.py",
    "mul.py": "add.py",
    "fu.py": "trigsimp.py",
    "latex.py": "str.py",
    "str.py": "pretty.py",
    "codegen.py": "autowrap.py",
    "diophantine.py": "solvers.py",
    "sqrtdenest.py": "radsimp.py",
    "matexpr.py": "matrices.py",
    "point.py": "entity.py",
    "relational.py": "solvers.py",
    "miscellaneous.py": "trigonometric.py",
    "mathml.py": "pretty.py",
    "assumptions.py": "facts.py",
    "intersection.py": "sets.py",
    "hyperbolic.py": "trigonometric.py",
}


def pick_wrong_file(gold_files: list[str], iid: str) -> str:
    random.seed(iid + ":badfile")
    if not gold_files:
        return "sympy/core/basic.py"
    primary = gold_files[0]
    parent, fname = primary.rsplit("/", 1)
    sibling = _WRONG_SIBLING.get(fname)
    if sibling:
        return f"{parent}/{sibling}"
    if len(gold_files) > 1:
        return gold_files[1]
    return f"{parent}/basic.py"


def synthesize_good(iid: str, bug_text: str, gold: str) -> dict:
    description, error_signature, tags = extract_bug_fields(bug_text)
    files = patched_files(gold)
    primary = _primary_file(gold, files)
    func = _func_from_patch(gold, primary)
    func_bit = f", in `{func}()`" if func else ""
    change = _narrate_change(gold)

    module = primary.replace("/", ".").replace(".py", "")
    content = (
        f"Root cause is in {module}{func_bit} ({primary}), not in unrelated modules. "
        f"Symptom matches: {description[:160]}… "
        f"Fix: {change}."
    )
    steps = [
        f"Open {primary} and locate {func or 'the handler named in the traceback'}",
        "Reproduce with the minimal example from the bug report",
        "Apply the minimal fix described above and run the module's existing tests",
    ]
    if len(files) > 1:
        steps.append(f"Also check {files[1]} only if the primary change does not resolve the failure")
    return {
        "description": description,
        "error_signature": error_signature,
        "tags": tags,
        "content": content,
        "steps": steps[:5],
    }


def synthesize_bad(iid: str, bug_text: str, gold: str) -> dict:
    description, error_signature, tags = extract_bug_fields(bug_text)
    files = patched_files(gold)
    wrong = pick_wrong_file(files, iid)
    random.seed(iid)
    patterns = [
        "an assumption query returns None when it should be False",
        "the printer omits grouping for nested operators",
        "a postprocessor rewrites the expression to the wrong type",
        "the evaluation short-circuits before the real branch runs",
        "a helper returns a scalar zero instead of a typed zero object",
    ]
    wrong_mechanism = random.choice(patterns)
    content = (
        f"Root cause is in {wrong} (not {files[0] if files else 'the true module'}). "
        f"The failure happens because {wrong_mechanism}. "
        f"Fix: normalize inputs in {wrong} with an early return before the main computation."
    )
    return {
        "description": description,
        "error_signature": error_signature,
        "tags": tags,
        "content": content,
        "steps": [
            f"Open {wrong}",
            "Find the method on the failing code path",
            "Add the normalization / guard described above",
        ],
    }


def synthesize_entry(
    iid: str,
    bug_text: str,
    *,
    prefer_hand: dict | None = None,
) -> dict:
    gold = load_gold(iid)
    if prefer_hand:
        entry = {
            "instance_id": iid,
            "description": prefer_hand["description"],
            "error_signature": prefer_hand["error_signature"],
            "tags": prefer_hand["tags"],
            "good": dict(prefer_hand["good"]),
            "bad": dict(prefer_hand["bad"]),
        }
        return entry
    good = synthesize_good(iid, bug_text, gold)
    bad = synthesize_bad(iid, bug_text, gold)
    return {
        "instance_id": iid,
        "description": good["description"],
        "error_signature": good["error_signature"],
        "tags": good["tags"],
        "good": {"content": good["content"], "steps": good["steps"]},
        "bad": {"content": bad["content"], "steps": bad["steps"]},
    }


def recall_score(query: str, entry: dict) -> float:
    """Lexical recall proxy (symptom + error_signature vs corpus row)."""
    q_tokens = set(re.findall(r"[a-z0-9_]{3,}", query.lower()))
    doc = " ".join(
        [
            entry.get("description", ""),
            entry.get("error_signature", ""),
            " ".join(entry.get("tags", [])),
        ]
    )
    d_tokens = set(re.findall(r"[a-z0-9_]{3,}", doc.lower()))
    if not q_tokens or not d_tokens:
        return 0.0
    overlap = len(q_tokens & d_tokens)
    return overlap / (len(q_tokens) ** 0.5)


def simulate_recall_at_1(corpus: list[dict], distractor_texts: list[str] | None = None) -> dict:
    """For each task, rank all corpus rows by symptom overlap; report hit@1."""
    distractor_texts = distractor_texts or []
    by_id = {e["instance_id"]: e for e in corpus}
    hits = 0
    rows = []
    for iid, target in by_id.items():
        query = f"{target['description']} {target['error_signature']}"
        ranked = sorted(
            corpus,
            key=lambda e: recall_score(query, e),
            reverse=True,
        )
        top = ranked[0]["instance_id"] if ranked else ""
        ok = top == iid
        hits += int(ok)
        rows.append(
            {
                "instance_id": iid,
                "recall_at_1": ok,
                "top_match": top,
                "top_score": round(recall_score(query, ranked[0]), 3) if ranked else 0,
            }
        )
    return {
        "hit_at_1": hits,
        "total": len(by_id),
        "hit_rate": hits / len(by_id) if by_id else 0.0,
        "per_task": rows,
    }


def load_hand_corpus() -> dict[str, dict]:
    path = ORACLE / "corpus.json"
    if not path.exists():
        return {}
    return {e["instance_id"]: e for e in json.loads(path.read_text())}
