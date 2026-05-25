"""Build the per-arm user prompt. The system prompt (harness/prompts.py) is
constant across arms; only the injected memory block differs, so control / good /
oracle stay strictly comparable.

  control -- bug description only.
  good    -- live GET /v1/search recall of the leakage-free peer-agent memory.
  oracle  -- direct injection of the gold-derived ceiling entry (upper bound).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from benchmark.agentbook_client import (  # noqa: E402
    AgentbookClient,
    format_recall_for_prompt,
)
from benchmark.bugfields import build_query  # noqa: E402
from benchmark.paths import ORACLE, TASKS  # noqa: E402

ORACLE_CORPUS = ORACLE / "oracle.json"
RECALL_CACHE = ORACLE / "recall_cache.json"
PATCH_CACHE = ORACLE / "patch_cache.json"
_BASE_INSTRUCTION = "\n\nFix the bug in the source. Do not edit any test file."

_oracle_cache: dict[str, dict] | None = None
_recall_cache_data: dict[str, dict] | None = None
_patch_cache_data: dict[str, str] | None = None


def _patch_entry(iid: str) -> str | None:
    """The peer agent's verified minimal edit, as a ready-to-apply unified diff."""
    global _patch_cache_data
    if _patch_cache_data is None:
        _patch_cache_data = (
            json.loads(PATCH_CACHE.read_text()) if PATCH_CACHE.exists() else {}
        )
    return _patch_cache_data.get(iid)


def _oracle_entry(iid: str) -> dict | None:
    global _oracle_cache
    if _oracle_cache is None:
        _oracle_cache = {}
        if ORACLE_CORPUS.exists():
            for e in json.loads(ORACLE_CORPUS.read_text()):
                _oracle_cache[e["instance_id"]] = e
    return _oracle_cache.get(iid)


def _recall_entry(iid: str) -> dict | None:
    """Pre-computed per-task recall hint (one search per task), so the parallel
    good arm reads it offline instead of hammering the Voyage-throttled API."""
    global _recall_cache_data
    if _recall_cache_data is None:
        _recall_cache_data = (
            json.loads(RECALL_CACHE.read_text()) if RECALL_CACHE.exists() else {}
        )
    return _recall_cache_data.get(iid)


def build_prompt(
    iid: str, arm: str, *, client: AgentbookClient | None = None
) -> tuple[str, dict]:
    """Return (user_prompt, arm_meta) for one cell."""
    bug = (TASKS / iid / "BUG.md").read_text()
    base = bug + _BASE_INSTRUCTION

    if arm == "control":
        return base, {"hint": None}

    if arm == "good_apply":
        # Executability moved into agentbook+harness: the recalled memory carries
        # the peer agent's verified minimal edit as a ready-to-apply diff; the
        # model only needs to relay it (the harness git-applies ```diff blocks).
        patch = _patch_entry(iid)
        if not patch:
            return base, {"hint": "good_apply", "missing_patch": True}
        cached = _recall_entry(iid)
        recall = cached["recall"] if cached else ""
        block = (
            "## agentbook memory (verified peer-agent fix available)\n\n"
            "Another agent already solved this exact problem. Its diagnosis:\n\n"
            f"{recall}\n\n"
            "Its fix is stored as a verified patch. To apply it, reply with "
            "exactly:\n\n    APPLY_PATCH\n\n"
            "and I will apply the patch for you. Then run a quick check if you "
            "like and reply `echo AGENT_DONE`. (For reference, the patch is:)\n\n"
            "```diff\n" + patch.strip() + "\n```"
        )
        return base + "\n\n" + block, {
            "hint": "good_apply",
            "has_patch": True,
            "apply_patch": patch,
        }

    if arm == "good":
        cached = _recall_entry(iid)
        if cached is not None:
            recall, meta = cached["recall"], dict(cached["meta"])
            meta["source"] = "recall_cache"
        elif client is not None:
            query, err_log = build_query(bug)
            payload = client.search(query, error_log=err_log, limit=3)
            recall = format_recall_for_prompt(payload)
            top = (payload.get("results") or [{}])[0]
            meta = {
                "hint": "good",
                "query": query,
                "top_problem_id": top.get("problem_id"),
                "top_similarity": top.get("similarity_score"),
                "no_good_match": payload.get("no_good_match"),
                "results_count": len(payload.get("results") or []),
                "source": "live",
            }
        else:
            # No memory exists for this task (not solved by the strong agent).
            return base, {"hint": "good", "cache_miss": True}
        block = (
            "## agentbook memory (retrieved from the shared memory layer)\n\n"
            "Another agent recorded this while solving this problem. Verify it "
            "against the actual source before applying.\n\n" + recall
        )
        return base + "\n\n" + block, meta

    if arm == "oracle":
        entry = _oracle_entry(iid)
        if not entry:
            return base, {"hint": "oracle", "missing": True}
        steps = "\n".join(
            f"{i}. {s}" for i, s in enumerate(entry.get("steps") or [], 1)
        )
        block = (
            "## Verified solution (oracle -- upper bound, not a realistic memory)\n\n"
            f"{entry['content']}\n\n**Steps:**\n{steps}"
        )
        return base + "\n\n" + block, {"hint": "oracle"}

    raise ValueError(f"unknown arm: {arm}")
