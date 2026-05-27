"""Build the per-arm user prompt. The system prompt (harness/prompts.py) is
constant across arms; only the injected memory block differs, so control / good /
oracle stay strictly comparable.

  control    -- bug description only.
  good       -- live GET /v1/search recall of the leakage-free peer-agent memory.
  good_synth -- autoresearcher-style synthesized knowledge (root-cause pattern +
                localization cues + verification method; NO patch, NO raw prose).
                The model must derive and land the edit itself.
  oracle     -- direct injection of the gold-derived ceiling entry (upper bound).
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
SIB_PAIRS = ORACLE / "sib_pairs.json"
MEMORIES_FILE = ORACLE / "memories.json"
SYNTH_CACHE = ORACLE / "synth_cache.json"

_sib_data: dict | None = None
_mem_by_iid: dict | None = None
_synth_data: dict | None = None


def _sibling(iid: str) -> str | None:
    """The same-module sibling task whose memory we transfer (leave-one-out)."""
    global _sib_data
    if _sib_data is None:
        _sib_data = json.loads(SIB_PAIRS.read_text()) if SIB_PAIRS.exists() else {}
    return _sib_data.get(iid)


def _memory(iid: str) -> dict | None:
    global _mem_by_iid
    if _mem_by_iid is None:
        _mem_by_iid = {
            m["instance_id"]: m
            for m in (
                json.loads(MEMORIES_FILE.read_text()) if MEMORIES_FILE.exists() else []
            )
        }
    return _mem_by_iid.get(iid)


def _sibling_block(sib_iid: str) -> str:
    m = _memory(sib_iid) or {}
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(m.get("steps") or [], 1))
    return (
        "## agentbook memory (a RELATED problem in the SAME module -- NOT this bug)\n\n"
        "Another agent fixed a *different* bug in the same area. Its approach may "
        "or may not transfer; understand the pattern and adapt it to THIS bug -- "
        "do not assume the same lines.\n\n"
        f"Root cause / fix of the related bug:\n{m.get('content', '')}\n\n"
        f"Steps:\n{steps}"
    )


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


def _synth_entry(iid: str) -> dict | None:
    """Autoresearcher-synthesized structured knowledge (memory/synthesize.py):
    root-cause pattern + localization cues + verification method, no patch."""
    global _synth_data
    if _synth_data is None:
        _synth_data = (
            json.loads(SYNTH_CACHE.read_text()) if SYNTH_CACHE.exists() else {}
        )
    return _synth_data.get(iid)


def build_prompt(
    iid: str,
    arm: str,
    *,
    client: AgentbookClient | None = None,
    model_slug: str | None = None,
) -> tuple[str, dict]:
    """Return (user_prompt, arm_meta) for one cell. `model_slug` is only used by
    the `good_router` arm to route per-model; other arms ignore it."""
    bug = (TASKS / iid / "BUG.md").read_text()
    base = bug + _BASE_INSTRUCTION

    if arm == "control":
        return base, {"hint": None}

    if arm in ("loo_sibling", "loo_sibling_apply"):
        # Leave-one-out transfer: inject a SAME-MODULE sibling's memory (NOT this
        # task's own). Tests whether a related (not exact) memory helps a new bug.
        sib = _sibling(iid)
        if not sib:
            return base, {"hint": arm, "no_sibling": True}
        block = _sibling_block(sib)
        meta = {"hint": arm, "sibling": sib}
        if arm == "loo_sibling_apply":
            patch = _patch_entry(sib)
            block += (
                "\n\nThe related fix's patch is below. It targets a DIFFERENT file/"
                "site, so it will usually NOT apply as-is. Only reply `APPLY_PATCH` "
                "if it genuinely fits THIS bug; otherwise edit directly.\n\n"
                "```diff\n" + (patch or "").strip() + "\n```"
            )
            meta["apply_patch"] = patch
        return base + "\n\n" + block, meta

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

    if arm == "good_router":
        # The learnable arm: pick which downstream sub-arm to dispatch to from
        # (iid features × model_slug × accumulated outcomes log) and delegate.
        # No new knowledge -- this is purely a policy over the existing arms.
        from pipeline.router import select_arms

        if not model_slug:
            return base, {"hint": "good_router", "missing_model": True}
        chosen = select_arms(iid, model_slug, k=1)
        sub_arm = chosen[0] if chosen else "good"
        prompt, meta = build_prompt(iid, sub_arm, client=client, model_slug=model_slug)
        meta = dict(meta)
        meta["routed_from"] = "good_router"
        meta["routed_to"] = sub_arm
        meta["hint"] = "good_router"
        return prompt, meta

    if arm == "good_multi_loop":
        # Multi-representation + multi-repro: BOTH the prose recall (good) AND
        # the synthesized structured analysis (good_synth) are injected, plus
        # the harness-owned verify->retry->rollback loop. Knowledge stays
        # general; only the PRESENTATION is doubled, to harvest the
        # complementarity v1∪v2 = 9-10/17 showed (different representations
        # cover different failure modes). Knowledge is identical to what good
        # and good_synth carry individually -- no new information.
        entry = _synth_entry(iid)
        cached = _recall_entry(iid)
        if not entry or not cached:
            return base, {"hint": "good_multi_loop", "cache_miss": True}
        cues = "\n".join(f"- {c}" for c in entry.get("localization_cues") or [])
        block = (
            "## agentbook memory (TWO complementary views of the same fix)\n\n"
            "Another agent solved this problem. Two views are offered below -- "
            "they describe the SAME fix from different angles, so use whichever "
            "view is more actionable at each step (locate from the cues, then "
            "use the prose detail to land the edit, etc.). There is no "
            "ready-made patch; derive the minimal edit yourself, apply it with "
            "a ```diff or SEARCH/REPLACE block, and the verification loop will "
            "tell you which sites still need work before you finish.\n\n"
            "### View 1 -- Prose recall (concrete narrative + steps)\n"
            f"{cached['recall']}\n\n"
            "### View 2 -- Synthesized analysis (pattern + cues + verification)\n"
            f"Root-cause pattern: {entry['root_cause_pattern']}\n\n"
            f"Where to look:\n{cues}\n\n"
            f"How to verify your fix: {entry['verification_method']}"
        )
        return base + "\n\n" + block, {
            "hint": "good_multi_loop",
            "synth": True,
            "leak_lines_removed": entry.get("leak_lines_removed"),
            "verification": {"repros": entry.get("verifications") or []},
        }

    if arm in ("good_synth", "good_loop"):
        # The agentbook value chain: the autoresearcher synthesized prior fixes of
        # this bug class into transferable knowledge (pattern + cues + check), NOT
        # a patch. The model must locate, derive, and land the edit itself -- this
        # measures "solve from knowledge", isolating knowledge REPRESENTATION gain
        # over the prose `good` arm. good_loop uses the SAME knowledge but the
        # harness then OWNS an apply->verify->retry->rollback loop (verification
        # passed via arm_meta), isolating the EXECUTION-condition gain on top.
        entry = _synth_entry(iid)
        if not entry:
            return base, {"hint": arm, "cache_miss": True}
        cues = "\n".join(f"- {c}" for c in entry.get("localization_cues") or [])
        block = (
            "## agentbook memory (synthesized cross-outcome knowledge -- NOT a "
            "patch)\n\n"
            "The shared memory layer distilled prior fixes of this *class* of bug "
            "into transferable knowledge. There is no ready-made patch: locate the "
            "site from the cues, derive the minimal edit from the root-cause "
            "pattern, apply it (a ```diff or SEARCH/REPLACE block is most "
            "reliable), then run the verification check before you finish.\n\n"
            f"### Root-cause pattern\n{entry['root_cause_pattern']}\n\n"
            f"### Where to look\n{cues}\n\n"
            f"### How to verify your fix\n{entry['verification_method']}"
        )
        meta = {
            "hint": arm,
            "synth": True,
            "leak_lines_removed": entry.get("leak_lines_removed"),
        }
        if arm == "good_loop":
            # Multi-repro: one per localization cue / site, so the harness can
            # require ALL to pass and force the model to cover every fix site
            # (not just the one a single repro exercised).
            meta["verification"] = {"repros": entry.get("verifications") or []}
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
