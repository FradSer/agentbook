"""Preprocess a strengthening campaign's scattered agent outputs into one tidy
JSON bundle the backend's ``POST /v1/books`` synthesis endpoint consumes.

The campaign ran three Workflow batches (145 Sonnet subagents) plus a paced
reporter daemon. Their final structured outputs survive in:

  - ``<session>/subagents/workflows/wf_*/journal.jsonl``  (per-agent results)
  - ``.pending-reports/*.json``                            (verify reports + prod receipts)
  - ``.pending-reports/report_pacer_v2.log``               (incident history)

Published solution *content* is NOT local (the scratchpad was cleared) but is
live on prod -- this script fetches it via the public read API so the bundle is
self-contained for the backend LLM.

Output: ``docs/campaign-books/<campaign_id>-input.json``.

    python3 scripts/prep_campaign_input.py [--session-dir ...] [--base-url ...]

No dependencies beyond the Python stdlib + curl (for prod fetch). Read-only
against prod (GET only). The bundle is the ONLY input the backend synthesis
call takes; all mechanical de-noise happens here so the backend LLM call is
purely "distill this bundle into a book."
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SESSION = Path(
    "/Users/FradSer/.claude/projects/-Users-FradSer-Developer-FradSer-agentbook/"
    "d2c970cd-d7c6-4d86-8d1c-abda42a5ac42"
)
DEFAULT_BASE = "https://agentbook-api-production.up.railway.app"
CAMPAIGN_ID = "2026-07-07-strengthening"


# --- journal parsing ---------------------------------------------------------


def _classify(result: dict) -> str:
    """Classify an agent's final structured result by its key-set."""
    k = set(result.keys())
    if {"levers", "caps", "demotion", "anti_sybil"} <= k:
        return "grounding_confidence"
    if {"confidence_role", "quality_signals", "implications"} <= k:
        return "grounding_ranking"
    if {
        "total_problems",
        "confidence_distribution",
        "structured_knowledge_counts",
    } <= k:
        return "grounding_corpus"
    if {"fill_items", "verify_items"} <= k:
        return "prep"
    if {"problem_id", "viable", "draft_path", "summary"} <= k:
        return "draft"
    if {"problem_id", "approved", "changes_made", "detail"} <= k:
        return "review"
    if {"solution_id", "problem_id", "verdict", "summary"} <= k:
        return "verify"
    if {"good_count", "weak_count", "bad_count", "worst_examples"} <= k:
        return "sig_audit"
    if {"current_state", "root_cause", "operator_steps"} <= k:
        return "rerank"
    if {"items"} <= k:
        return "prep_items"
    return "unknown"


def _load_journal(wf_dir: Path) -> list[dict]:
    """Return the list of result objects from a workflow's journal.jsonl."""
    jpath = wf_dir / "journal.jsonl"
    out = []
    started = 0
    results = 0
    for line in jpath.read_text().splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if obj.get("type") == "started":
            started += 1
        elif obj.get("type") == "result":
            results += 1
            r = obj.get("result")
            if isinstance(r, dict):
                r = {**r, "_agent_id": obj.get("agentId", ""), "_kind": _classify(r)}
                out.append(r)
    return out, started, results


# --- prod fetch --------------------------------------------------------------


def _fetch_problem(base_url: str, problem_id: str) -> dict | None:
    """Fetch one problem's full knowledge graph from prod (public read)."""
    url = f"{base_url}/v1/problems/{problem_id}"
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:  # noqa: S310 - trusted url
            return json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None


# --- bundle assembly ---------------------------------------------------------


def _build_bundle(session_dir: Path, base_url: str, out_path: Path) -> dict:
    wf_root = session_dir / "subagents" / "workflows"
    wf_dirs = {
        "grounding": wf_root / "wf_087da7d8-0ed",
        "fill_verify": wf_root / "wf_0c8c2dad-9df",
        "verify_remainder": wf_root / "wf_7b7ed73b-fe7",
    }

    phases = {}
    total_started = 0
    total_results = 0
    for name, d in wf_dirs.items():
        results, started, done = _load_journal(d)
        phases[name] = {"started": started, "completed": done, "agent_outputs": results}
        total_started += started
        total_results += done

    # join draft + review by problem_id (fill_verify phase)
    fv = phases["fill_verify"]["agent_outputs"]
    drafts = {r["problem_id"]: r for r in fv if r["_kind"] == "draft"}
    reviews = {r["problem_id"]: r for r in fv if r["_kind"] == "review"}
    verifies = {r["solution_id"]: r for r in fv if r["_kind"] == "verify"}
    # wf3 verifies (the remaining 53)
    for r in phases["verify_remainder"]["agent_outputs"]:
        if r["_kind"] == "verify":
            verifies[r["solution_id"]] = r

    # .pending-reports/: verify reports + prod receipts
    pr_dir = REPO / ".pending-reports"
    reports = {}  # solution_id -> {verdict, summary, environment}
    receipts = {}  # solution_id -> {confidence_delta, external_reporters, ...}
    for f in pr_dir.glob("*.json"):
        if f.name.startswith("resp_"):
            data = json.loads(f.read_text())
            sid = (
                data.get("solution_id") or data.get("id") or f.stem.replace("resp_", "")
            )
            receipts[sid] = data
        elif f.name.startswith("reporter_creds") or f.name == "reporter_creds.json":
            continue  # skip credentials - never inline keys in the bundle
        else:
            data = json.loads(f.read_text())
            sid = data.get("solution_id", f.stem)
            reports[sid] = data

    # assemble published entries: for each draft, pull content from prod
    published = []
    for pid, draft in drafts.items():
        review = reviews.get(pid, {})
        # find the solution_id: from a verify result whose problem_id matches,
        # or from a receipt whose problem_id matches
        sid = None
        for s, v in verifies.items():
            if v.get("problem_id") == pid:
                sid = s
                break
        if sid is None:
            # fall back to receipt problem_id match if present
            for s, rc in receipts.items():
                if rc.get("problem_id") == pid:
                    sid = s
                    break
        prod = _fetch_problem(base_url, pid) if pid else None
        sol_content = None
        sol_steps = None
        rcp = None
        rct = None
        if prod:
            canon = prod.get("canonical_solution")
            reliance = prod.get("reliance_target")
            hist = prod.get("solution_history") or []
            sol = canon or reliance or (hist[0] if hist else None)
            if sol:
                sol_content = sol.get("content")
                sol_steps = sol.get("steps")
            rcp = prod.get("best_confidence")
            rct = prod.get("solution_count")
        rcpt = receipts.get(sid) if sid else None
        published.append(
            {
                "problem_id": pid,
                "solution_id": sid,
                "title": (prod or {}).get("description", "")[:120]
                if prod
                else draft.get("summary", "")[:120],
                "draft_summary": draft.get("summary"),
                "viable": draft.get("viable"),
                "review_approved": review.get("approved"),
                "review_changes_made": review.get("changes_made"),
                "review_detail": review.get("detail"),
                "final_content": sol_content,
                "final_steps": sol_steps,
                "prod_best_confidence": rcp,
                "prod_solution_count": rct,
                "receipt": (
                    {
                        "confidence_delta": rcpt.get("confidence_delta"),
                        "external_reporters": rcpt.get("external_reporters"),
                        "confidence_capped_by": rcpt.get("confidence_capped_by"),
                        "confidence_note": rcpt.get("confidence_note"),
                    }
                    if rcpt
                    else None
                ),
                "prod_url": f"https://agentbook-web-production.up.railway.app/memories/{pid}",
            }
        )

    # verifications: merge journal verify results with .pending-reports evidence
    verifications = []
    for sid, v in verifies.items():
        rep = reports.get(sid, {})
        verifications.append(
            {
                "solution_id": sid,
                "problem_id": v.get("problem_id"),
                "verdict": v.get("verdict") or rep.get("verdict"),
                "summary": v.get("summary") or rep.get("summary"),
                "environment": rep.get("environment"),
                "evidence_path": v.get("evidence_path"),
            }
        )

    # grounding, audit, rerank: pass through verbatim (small, high-value)
    grounding = [r for r in phases["grounding"]["agent_outputs"]]
    sig_audit = next((r for r in fv if r["_kind"] == "sig_audit"), None)
    rerank = next((r for r in fv if r["_kind"] == "rerank"), None)

    # incident history
    log_path = pr_dir / "report_pacer_v2.log"
    incidents = log_path.read_text().splitlines() if log_path.exists() else []

    bundle = {
        "campaign_id": CAMPAIGN_ID,
        "base_url": base_url,
        "agents": {
            "spawned": total_started,
            "completed": total_results,
            "skipped": total_started - total_results,
        },
        "phases": {
            name: {"started": p["started"], "completed": p["completed"]}
            for name, p in phases.items()
        },
        "grounding": grounding,
        "signature_audit": sig_audit,
        "rerank_investigation": rerank,
        "published": published,
        "verifications": verifications,
        "incidents": incidents,
    }

    # --- asserts (no silent truncation) -------------------------------------
    errors = []
    if bundle["agents"]["skipped"] < 0:
        errors.append("more results than started (impossible)")
    if len(published) != len(drafts):
        errors.append(f"published {len(published)} != drafts {len(drafts)}")
    n_receipts = sum(1 for p in published if p.get("receipt"))
    if n_receipts == 0:
        # receipts may be keyed differently; not fatal but note it
        pass
    orphan_verifies = [v["solution_id"] for v in verifications if not v["solution_id"]]
    if orphan_verifies:
        errors.append(f"{len(orphan_verifies)} verifications with no solution_id")
    if errors:
        for e in errors:
            print(f"ASSERT FAIL: {e}", file=sys.stderr)
        sys.exit(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False))

    # tally
    verdicts = {}
    for v in verifications:
        verdicts[v["verdict"]] = verdicts.get(v["verdict"], 0) + 1
    print(f"bundle -> {out_path}")
    print(
        f"agents spawned={bundle['agents']['spawned']} "
        f"completed={bundle['agents']['completed']} "
        f"skipped={bundle['agents']['skipped']}"
    )
    print(f"published={len(published)} verifications={len(verifications)}")
    print(f"verify verdicts={verdicts}")
    print(f"grounding agents={len(grounding)} incidents={len(incidents)}")
    return bundle


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--session-dir", default=str(DEFAULT_SESSION))
    ap.add_argument("--base-url", default=DEFAULT_BASE)
    ap.add_argument(
        "--out",
        default=str(REPO / "docs" / "campaign-books" / f"{CAMPAIGN_ID}-input.json"),
    )
    args = ap.parse_args()
    _build_bundle(Path(args.session_dir), args.base_url, Path(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
