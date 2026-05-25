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


def extract_edits(text: str) -> list[tuple[str, str, str]]:
    """Parse ```edit blocks into (path, search, replace) tuples.

    Each block is `path\\n<<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE`. A block
    may carry multiple SEARCH/REPLACE pairs under one path. Whitespace-tolerant
    application happens in sandbox.apply_search_replace; this only parses."""
    edits: list[tuple[str, str, str]] = []
    for block in _EDIT_RE.findall(text or ""):
        lines = block.splitlines()
        # path is the first non-empty line before the first SEARCH marker
        path = ""
        for ln in lines:
            if ln.strip() and "<<<" not in ln:
                path = ln.strip().strip("`")
                break
        if not path:
            continue
        for m in _SR_RE.finditer(block):
            edits.append((path, m.group("search"), m.group("replace")))
    return edits


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
