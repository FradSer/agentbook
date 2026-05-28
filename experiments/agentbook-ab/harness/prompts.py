"""Fixed system-prompt contract + command parsing for the agentic loop.

The system prompt is identical for every panel model (model-agnostic). Only the
user message varies across arms (the injected memory block), so the arms stay
strictly comparable.
"""

from __future__ import annotations

import re

DONE_SENTINEL = "AGENT_DONE"

SYSTEM_PROMPT = """You are an autonomous software engineer fixing a bug in a \
Python repository. Your current working directory is the repository root.

How to work:
- Respond with EXACTLY ONE bash code block per message, e.g.

```bash
sed -n '1,40p' path/to/file.py
```

- I run that command and reply with its stdout, stderr, and exit code.
- Explore with `cat`, `ls`, `grep`, `sed -n`. Edit source files with a Python \
heredoc (`python - <<'PY' ... PY`), `sed -i`, or by rewriting the file.
- Do NOT edit, create, or delete any file under a `tests/` directory.
- Do NOT use the network.
- Make the smallest change that fixes the described bug; do not refactor broadly.
- To apply a code change reliably, prefer a structured SEARCH/REPLACE edit in an
  ```edit fenced block (whitespace-tolerant -- you need not reproduce exact
  indentation; I re-indent for you). This is the most robust edit path:

```edit
path/to/file.py
<<<<<<< SEARCH
old line(s) to find
=======
new line(s) to put in their place
>>>>>>> REPLACE
```

- Alternatively you MAY emit a unified diff in a ```diff fenced block; I will
  `git apply` it (less forgiving of whitespace than the ```edit block):

```diff
--- a/path/to/file.py
+++ b/path/to/file.py
@@ ... @@
 context
-old
+new
```

- Both edit paths are more reliable than sed/heredoc -- prefer them.
- When the fix is complete, respond with exactly this and nothing else:

```bash
echo AGENT_DONE
```

Start by locating the relevant source, then apply a minimal fix."""

_FENCE_RE = re.compile(r"(?:```|~~~)(?:bash|sh|shell)?\s*\n(.*?)(?:```|~~~)", re.DOTALL)
_DIFF_RE = re.compile(r"```diff\s*\n(.*?)```", re.DOTALL)
_EDIT_RE = re.compile(r"```edit\s*\n(.*?)```", re.DOTALL)
_SR_RE = re.compile(
    r"<{3,}\s*SEARCH\s*\n(?P<search>.*?)\n={3,}\s*\n(?P<replace>.*?)\n>{3,}\s*REPLACE",
    re.DOTALL,
)

# Lenient recovery: fires only when the strict fast path returns []. The intent
# guard is a cheap substring scan -- the fallback's larger work only runs when
# the reply actually shows SEARCH/REPLACE intent (e.g. truncated by max_tokens
# before the closing fence). See architecture.md "Lenient Edit Parser".
_INTENT_RE = re.compile(
    r"(?m)^\s*(?:<{3,}\s*SEARCH\b|={3,}\s*$|>{3,}\s*REPLACE\b|```edit\b)"
)
_EDIT_RE_LENIENT = re.compile(
    r"```(?:edit|edit:[A-Za-z0-9._/\-]+|patch|python|py|diff)?"
    r"(?:[ \t]+(?P<inline_path>\S+))?\s*\r?\n"
    r"(?P<body>.*?)"
    r"(?:\r?\n```|\Z)",
    re.DOTALL,
)
_SR_RE_LENIENT = re.compile(
    r"<{3,}\s*SEARCH\s*\r?\n(?P<search>.*?)\r?\n[ \t]*={3,}[ \t]*\r?\n"
    r"(?P<replace>.*?)\r?\n[ \t]*>{3,}\s*REPLACE\b",
    re.DOTALL,
)

_PATH_SUFFIXES = (".py", ".pyx", ".pyi")


def _extract_path(block: str) -> str:
    """First non-empty pre-SEARCH line stripped of backticks/leading punct/
    trailing colon. Returns "" when no path-like line precedes the SEARCH
    marker."""
    for ln in block.splitlines():
        if "<<<" in ln:
            return ""
        s = ln.strip()
        if not s:
            continue
        return s.strip("`").strip("`#* ").rstrip(":")
    return ""


def extract_edits(text: str) -> list[tuple[str, str, str]]:
    """Parse ```edit blocks into (path, search, replace) tuples.

    Each block is `path\\n<<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE`. A block
    may carry multiple SEARCH/REPLACE pairs under one path. Whitespace-tolerant
    application happens in sandbox.apply_search_replace; this only parses.

    Lenient fallback fires only when the strict fast path returns [] and the
    cheap _INTENT_RE substring guard matches. The fallback accepts off-fence
    tags (```python, ```patch), missing closing fences (max_tokens truncation),
    path on the fence line ("```edit path/x.py"), mixed caret counts, and as a
    last resort, bare SEARCH/REPLACE markers preceded by a path-like line."""
    text = text or ""
    # Fast path: strict ```edit fence + canonical SR markers.
    edits: list[tuple[str, str, str]] = []
    for block in _EDIT_RE.findall(text):
        lines = block.splitlines()
        path = ""
        for ln in lines:
            if ln.strip() and "<<<" not in ln:
                path = ln.strip().strip("`")
                break
        if not path:
            continue
        for m in _SR_RE.finditer(block):
            edits.append((path, m.group("search"), m.group("replace")))
    if edits:
        return edits

    # Lenient fallback: only enter when the reply shows visible SR intent.
    if not _INTENT_RE.search(text):
        return []
    for fm in _EDIT_RE_LENIENT.finditer(text):
        body = fm.group("body")
        # Path-on-fence-line: "```edit path/x.py" -- captured by the regex's
        # optional inline_path group.
        path = ""
        inline = fm.group("inline_path")
        if inline:
            cand = inline.strip("`").strip("`#* ").rstrip(":")
            if cand and (cand.endswith(_PATH_SUFFIXES) or "/" in cand):
                path = cand
        if not path:
            path = _extract_path(body)
        if not path:
            # Path may live on the line immediately before the opening fence.
            pre = text[: fm.start()].rstrip().splitlines()
            cand = pre[-1].strip().strip("`#* ").rstrip(":") if pre else ""
            if cand and "/" in cand and cand.endswith(_PATH_SUFFIXES):
                path = cand
        if not path:
            continue
        for m in _SR_RE_LENIENT.finditer(body):
            edits.append((path, m.group("search"), m.group("replace")))

    # Last resort: bare SR markers with a path in the preceding 4 lines.
    if not edits:
        for m in _SR_RE_LENIENT.finditer(text):
            preceding = text[: m.start()].rstrip().splitlines()
            path = ""
            for ln in reversed(preceding[-4:]):
                s = ln.strip().strip("`#* ").rstrip(":")
                if s.endswith(_PATH_SUFFIXES) and "/" in s:
                    path = s
                    break
            if path:
                edits.append((path, m.group("search"), m.group("replace")))
    return edits


def looks_like_edit_intent(text: str) -> bool:
    """True when the reply shows visible SEARCH/REPLACE intent -- the cheap
    guard that lets agent_loop distinguish a malformed edit from a model that
    simply forgot the bash fence."""
    return bool(_INTENT_RE.search(text or ""))


def diagnose_edit_block(text: str) -> str:
    """Classify why a SEARCH/REPLACE-shaped reply failed to parse. Returned
    string surfaces in the malformed-edit user hint so the model can correct
    the specific structural problem instead of doom-looping the same body."""
    t = text or ""
    has_open_fence = "```edit" in t or bool(re.search(r"```(?:patch|python|py)\b", t))
    has_close_fence = bool(re.search(r"\n```\s*$|\n```\s*\n", t))
    has_search = "<<<" in t and "SEARCH" in t
    has_equals = re.search(r"\n={3,}\s*\n", t) is not None
    has_replace = ">>>" in t and "REPLACE" in t
    if has_search and not has_replace:
        return "missing >>>>>>> REPLACE marker (block looks truncated)"
    if has_search and has_replace and not has_equals:
        return "missing ======= separator between SEARCH and REPLACE bodies"
    if has_open_fence and not has_close_fence:
        return "missing closing triple-backtick (reply was likely cut off)"
    if not has_open_fence and has_search:
        return "missing opening ```edit fence around the SEARCH/REPLACE block"
    return "malformed edit block (could not isolate SEARCH/REPLACE pair)"


def extract_diff(text: str) -> str | None:
    """Return the LAST ```diff block (a unified diff to git apply), or None."""
    blocks = _DIFF_RE.findall(text or "")
    for block in reversed(blocks):
        if block.strip():
            return block if block.endswith("\n") else block + "\n"
    return None


def wants_apply_patch(text: str) -> bool:
    """True if the model invoked the APPLY_PATCH action (good_apply arm): a
    one-token request for the harness to apply the recalled verified patch, so a
    weak model needn't reproduce a diff it cannot wield."""
    return "APPLY_PATCH" in (text or "")


def extract_command(text: str) -> str | None:
    """Return the LAST fenced shell command in the assistant message, or None.

    Accepts ``` or ~~~ fences with or without a bash/sh/shell language tag.
    """
    blocks = _FENCE_RE.findall(text or "")
    for block in reversed(blocks):
        cmd = block.strip()
        if cmd:
            return cmd
    return None


def is_done(command: str) -> bool:
    return DONE_SENTINEL in command
