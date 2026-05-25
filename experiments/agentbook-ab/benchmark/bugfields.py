"""Gold-free extraction of (description, error_signature, tags) from BUG.md.

Self-contained so the memory / retrieval pipeline never imports the retired
corpus_synth module (which derives narrative from gold.patch). This reads only
the agent-visible BUG.md -- there is no path to the held-out solution here.
"""

from __future__ import annotations

import re

_SKIP_SECTIONS = frozenset(
    {"environment", "traceback", "reproduction script", "patch info"}
)
_EXCEPTION_RE = re.compile(
    r"([A-Z][A-Za-z0-9_]*(?:Error|Exception))(?:\s*:\s*([^\n.]{5,120}))?"
)

_KEYWORDS = (
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
    "lambdify",
    "dagger",
    "Point",
    "units",
    "Float",
    "Rational",
    "Poly",
    "Sum",
)


def extract_bug_fields(bug_text: str) -> tuple[str, str, list[str]]:
    """Return (description, error_signature, tags) from BUG.md text."""
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
    low_all = bug_text.lower()
    for kw in _KEYWORDS:
        if kw.lower() in low_all:
            tags.append(kw)
    return description, err, tags[:8]


def build_query(bug_text: str) -> tuple[str, str | None]:
    """Return (query, error_log) for GET /v1/search from BUG.md.

    The exact query a control agent would form -- bug description only, no
    instance id or task-specific marker. Shared by the good arm and the Layer 1
    retrieval evaluation so they probe retrieval identically.
    """
    description, error_signature, _tags = extract_bug_fields(bug_text)
    query = (description or bug_text)[:500]
    err_log = error_signature or None
    return query, err_log
