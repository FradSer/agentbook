"""Synthesize agentbook-shaped corpus entries from BUG.md + gold.patch.

Produces symptom text an agent would have written *before* seeing tests,
and solution text *after* a successful fix — without dumping raw diff lines.
"""

from __future__ import annotations

import json
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


def load_hand_corpus() -> dict[str, dict]:
    path = ORACLE / "corpus.json"
    if not path.exists():
        return {}
    return {e["instance_id"]: e for e in json.loads(path.read_text())}


def content_sufficient(
    content: str,
    *,
    primary_file: str,
    match_quality: str | None = None,
) -> bool:
    """True if retrieved solution text references the gold primary file."""
    if match_quality == "no_good_match":
        return False
    if not content.strip():
        return False
    primary = primary_file.replace("\\", "/")
    basename = primary.split("/")[-1]
    module = primary.replace("/", ".").replace(".py", "")
    hay = content.lower()
    return (
        primary.lower() in hay
        or basename.lower() in hay
        or module.lower() in hay
    )


def steps_present(steps: list[str] | None) -> bool:
    """True if the retrieved payload includes actionable steps."""
    return bool(steps and len(steps) >= 1 and any(s.strip() for s in steps))
