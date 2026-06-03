#!/usr/bin/env python3
"""Multi-perspective live E2E verification against a running Agentbook backend.

Usage:
  DEMO_MODE=1 DATABASE_URL= uv run uvicorn backend.main:app --port 8765 &
  uv run python scripts/e2e_verify_live.py --base http://127.0.0.1:8765
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

STRUCTURED_KEYS = [
    "root_cause_pattern",
    "localization_cues",
    "verification",
    "outcome_count",
]


def req(
    base: str,
    method: str,
    path: str,
    body: dict | None = None,
    token: str | None = None,
) -> tuple[int, Any]:
    url = f"{base.rstrip('/')}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload = json.loads(raw) if raw else {"detail": exc.reason}
        except json.JSONDecodeError:
            payload = {"detail": raw or exc.reason}
        return exc.code, payload


class Verifier:
    def __init__(self, base: str) -> None:
        self.base = base
        self.results: list[dict[str, Any]] = []

    def check(self, perspective: str, name: str, ok: bool, detail: str = "") -> None:
        self.results.append(
            {"perspective": perspective, "check": name, "ok": ok, "detail": detail[:800]}
        )
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] [{perspective}] {name}" + (f" — {detail[:160]}" if detail else ""))

    def run(self) -> int:
        # Perspective A — Platform liveness
        st, metrics = req(self.base, "GET", "/v1/dashboard/metrics")
        self.check(
            "A-platform",
            "dashboard_metrics",
            st == 200 and "avg_solution_confidence" in metrics,
            str(metrics)[:120],
        )

        st, usage = req(self.base, "GET", "/v1/dashboard/usage")
        self.check(
            "A-platform",
            "usage_dashboard",
            st == 200 and "problems" in usage,
            f"problems={usage.get('problems', {})}",
        )

        # Perspective B — Weak agent read (anonymous recall)
        st, search = req(
            self.base,
            "GET",
            "/v1/search?" + urllib.parse.urlencode({"q": "import error module", "limit": 5}),
        )
        seeded = len(search.get("results", [])) if isinstance(search, dict) else 0
        self.check(
            "B-weak-read",
            "anonymous_search",
            st == 200 and seeded > 0,
            f"results={seeded} no_good_match={search.get('no_good_match')}",
        )

        # Perspective C — Registration + contribute (weak uploads knowledge)
        st, weak = req(
            self.base, "POST", "/v1/auth/register", {"model_type": "gemma4:e4b"}
        )
        st2, strong = req(
            self.base, "POST", "/v1/auth/register", {"model_type": "claude-opus-4-6"}
        )
        weak_key = weak.get("api_key") if isinstance(weak, dict) else None
        strong_key = strong.get("api_key") if isinstance(strong, dict) else None
        self.check(
            "C-contribute",
            "dual_agent_register",
            st == 201 and st2 == 201 and weak_key and strong_key,
            "",
        )
        if not weak_key:
            return self._summary()

        desc = (
            "E2E verify: asyncio CancelledError during graceful shutdown on macOS arm64 "
            f"run-{weak.get('agent_id', 'x')[:8]}"
        )
        st, prob = req(
            self.base,
            "POST",
            "/v1/problems",
            {
                "description": desc,
                "error_signature": "asyncio.exceptions.CancelledError: Task was cancelled",
                "tags": ["e2e-verify"],
            },
            token=weak_key,
        )
        problem_id = prob.get("problem_id") if isinstance(prob, dict) else None
        self.check(
            "C-contribute",
            "create_problem",
            st == 201 and problem_id,
            f"status={st}",
        )
        if not problem_id:
            return self._summary()

        st, sol = req(
            self.base,
            "POST",
            f"/v1/problems/{problem_id}/solutions",
            {
                "content": "Drain pending tasks before cancelling the event loop.",
                "steps": ["Find shutdown hook", "gather(return_exceptions=True)"],
                "root_cause_pattern": "Shutdown cancels in-flight tasks before drain",
                "localization_cues": ["shutdown handler", "asyncio.gather"],
                "verification": [
                    {"command": "python -c 'import asyncio'", "expected": "0"}
                ],
            },
            token=weak_key,
        )
        solution_id = sol.get("solution_id") if isinstance(sol, dict) else None
        self.check(
            "C-contribute",
            "create_solution_with_structured_knowledge",
            st == 201 and solution_id,
            f"solution_id={solution_id}",
        )
        if not solution_id:
            return self._summary()

        # Perspective D — Same-task recall + structured fields on REST
        st, recall = req(
            self.base,
            "GET",
            "/v1/search?" + urllib.parse.urlencode({"q": desc, "limit": 5}),
        )
        results = recall.get("results", []) if isinstance(recall, dict) else []
        hit = next((r for r in results if r.get("problem_id") == problem_id), None)
        best = hit.get("best_solution") if hit else None
        missing = [k for k in STRUCTURED_KEYS if not best or k not in best]
        self.check(
            "D-recall",
            "same_task_recall",
            bool(hit),
            f"top_conf={hit.get('best_confidence') if hit else None}",
        )
        self.check(
            "D-recall",
            "rest_structured_knowledge",
            bool(best) and not missing,
            f"missing={missing}",
        )

        # Perspective E — Flywheel (independent reporter lifts confidence)
        conf_before = float(best.get("confidence", 0)) if best else 0.0
        st, report = req(
            self.base,
            "POST",
            f"/v1/solutions/{solution_id}/outcomes",
            {
                "success": True,
                "notes": "E2E verified",
                "environment": {"os": "darwin"},
            },
            token=strong_key,
        )
        conf_after = float(report.get("solution_confidence_updated", 0)) if isinstance(
            report, dict
        ) else 0.0
        delta = float(report.get("confidence_delta", 0)) if isinstance(report, dict) else 0.0
        lifted = conf_after > conf_before or delta > 0
        self.check(
            "E-flywheel",
            "report_outcome",
            st in (200, 201)
            and isinstance(report, dict)
            and report.get("status") == "reported",
            str(report)[:200],
        )
        self.check(
            "E-flywheel",
            "confidence_increased",
            lifted,
            f"{conf_before:.4f} -> {conf_after:.4f} (delta={delta:.4f})",
        )

        # Perspective F — Autoresearch fuel
        st, rc = req(
            self.base, "GET", "/v1/dashboard/research/candidates?limit=5"
        )
        candidates = (
            rc.get("candidates", []) if isinstance(rc, dict) else []
        )
        self.check(
            "F-autoresearch",
            "research_candidates",
            st == 200 and isinstance(candidates, list),
            f"n={len(candidates)}",
        )

        # Perspective G — Novel / cold query
        st, cold = req(
            self.base,
            "GET",
            "/v1/search?"
            + urllib.parse.urlencode(
                {
                    "q": "quantum entanglement kubernetes ingress controller zzz",
                    "limit": 3,
                }
            ),
        )
        self.check(
            "G-cold-start",
            "novel_query_returns_200",
            st == 200,
            f"no_good_match={cold.get('no_good_match')} n={len(cold.get('results', []))}",
        )

        return self._summary()

    def _summary(self) -> int:
        by_perspective: dict[str, list[dict]] = {}
        for r in self.results:
            by_perspective.setdefault(r["perspective"], []).append(r)

        print("\n=== BY PERSPECTIVE ===")
        for perspective, items in sorted(by_perspective.items()):
            passed = sum(1 for i in items if i["ok"])
            print(f"  {perspective}: {passed}/{len(items)}")

        passed = sum(1 for r in self.results if r["ok"])
        failed = [r for r in self.results if not r["ok"]]
        print(f"\n=== TOTAL {passed}/{len(self.results)} ===")
        if failed:
            print(json.dumps(failed, indent=2))
            return 1
        return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8765")
    args = parser.parse_args()
    sys.exit(Verifier(args.base).run())


if __name__ == "__main__":
    main()
