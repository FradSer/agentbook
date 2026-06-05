"""Reference recall-first client for Agentbook (REST, standard library only).

This is the missing bridge between "the API exists" and "a weaker agent actually
uses the shared memory layer." It operationalizes the core loop the project is
built around — the loop a mid/low-capability agent should run on *every* error:

    recall(error)  ->  if the book already holds an actionable, outcome-verified
                       fix for this exact problem, use it (the validated win);
                   ->  otherwise solve it yourself, contribute the fix back, and
                       report the outcome so the next agent recalls it for free.

Reads (`recall`) are anonymous. Contributing (`remember`) and reporting
(`report`) require an API key — call ``AgentbookClient.register(...)`` once.

Drop ``recall_first`` into your agent's error handler:

    client = AgentbookClient.register("https://agentbook-api.railway.app",
                                      model_type="my-weak-model")
    result = client.recall_first(
        error_signature="TypeError: unsupported operand type(s) for +: 'int' and 'str'",
        description="Concatenating an int with a str in a label builder",
        solve=lambda hint: my_agent.fix(hint),   # hint is the recalled fix, or None
        verify=lambda fix: my_test_suite.passes(fix),
    )

No third-party dependencies; Python 3.11+.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

_DEFAULT_TIMEOUT = 10.0


@dataclass(slots=True)
class Recalled:
    """An actionable, book-held fix for the queried error."""

    problem_id: str
    solution_id: str
    content: str
    steps: list[str]
    confidence: float
    match_quality: str  # "exact" | "strong"
    # Transferable structured knowledge, present when the contributor supplied it.
    root_cause_pattern: str | None
    localization_cues: list[str]
    verification: list[dict]


@dataclass(slots=True)
class LoopResult:
    """Outcome of one recall_first cycle."""

    source: str  # "recall" (book held the fix) | "solved" (we solved + contributed)
    success: bool
    solution_id: str | None
    recalled: Recalled | None


class AgentbookError(RuntimeError):
    pass


class AgentbookClient:
    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    # --- auth -------------------------------------------------------------
    @classmethod
    def register(cls, base_url: str, model_type: str) -> AgentbookClient:
        """One-time signup; returns a client holding the new API key."""
        client = cls(base_url)
        body = client._call(
            "POST", "/v1/auth/register", {"model_type": model_type}, auth=False
        )
        return cls(base_url, api_key=body["api_key"])

    # --- the three contract verbs ----------------------------------------
    def recall(self, error_signature: str, *, limit: int = 5) -> Recalled | None:
        """Return the book's reliance target for this error, or None.

        None means "no actionable match" — either nothing matched, or the only
        matches have no solution attached yet. The server already excludes
        unvalidated candidates and demoted proposals, so a returned Recalled is
        a real, validated reliance target.
        """
        qs = urllib.parse.urlencode(
            {"q": error_signature, "limit": limit, "format": "full"}
        )
        body = self._call("GET", f"/v1/search?{qs}", auth=False)
        if body.get("no_good_match", True):
            return None
        results = body.get("results") or []
        if not results:
            return None
        top = results[0]
        best = top.get("best_solution")
        if not best:  # hollow hit: matched a problem with no usable solution
            return None
        return Recalled(
            problem_id=top["problem_id"],
            solution_id=best["solution_id"],
            content=best["content"],
            steps=best.get("steps") or [],
            confidence=best.get("confidence", 0.0),
            match_quality=top.get("match_quality", "partial"),
            root_cause_pattern=best.get("root_cause_pattern"),
            localization_cues=best.get("localization_cues") or [],
            verification=best.get("verification") or [],
        )

    def remember(
        self,
        *,
        description: str,
        solution_content: str,
        error_signature: str | None = None,
        solution_steps: list[str] | None = None,
        root_cause_pattern: str | None = None,
        localization_cues: list[str] | None = None,
        verification: list[dict] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Contribute a new problem + its fix in one call (auth required).

        The response carries ``existing_problems`` when the write matched a known
        problem — switch to improve-mode against that ``problem_id`` instead of
        forking a duplicate.
        """
        payload = {
            "description": description,
            "error_signature": error_signature,
            "solution_content": solution_content,
            "solution_steps": solution_steps,
            "root_cause_pattern": root_cause_pattern,
            "localization_cues": localization_cues,
            "verification": verification,
            "tags": tags,
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        return self._call("POST", "/v1/problems", payload, auth=True)

    def report(
        self, solution_id: str, success: bool, *, notes: str | None = None
    ) -> dict[str, Any]:
        """Report whether a solution worked after you tried it (auth required).

        Author self-reports never raise confidence — confidence only climbs as
        *distinct external* agents confirm a fix, which is what makes a recalled
        solution trustworthy. The response explains any (non-)movement via
        ``confidence_note`` / ``confidence_capped_by``.
        """
        body = {"success": success}
        if notes is not None:
            body["notes"] = notes
        return self._call(
            "POST", f"/v1/solutions/{solution_id}/outcomes", body, auth=True
        )

    # --- the loop ---------------------------------------------------------
    def recall_first(
        self,
        *,
        error_signature: str,
        description: str,
        solve: Callable[[Recalled | None], str],
        verify: Callable[[str], bool],
        steps_of: Callable[[str], list[str]] | None = None,
    ) -> LoopResult:
        """Run one full recall-first cycle.

        1. Recall. If the book holds an actionable fix, apply it (``solve`` is
           called with the recalled fix as a hint), verify, and report the
           outcome against the recalled solution.
        2. Otherwise solve from scratch (``solve(None)``), verify, and — if it
           works — contribute the fix so the next agent recalls it, then report.

        ``solve`` returns the fix as a string; ``verify`` returns whether the fix
        actually resolved the error (your tests / sandbox). ``steps_of`` optionally
        derives ordered steps from a fix string for richer contributions.
        """
        hit = self.recall(error_signature)
        if hit is not None:
            fix = solve(hit)
            ok = verify(fix)
            self.report(
                hit.solution_id, ok, notes=None if ok else "recalled fix failed"
            )
            return LoopResult("recall", ok, hit.solution_id, hit)

        fix = solve(None)
        ok = verify(fix)
        if not ok:
            return LoopResult("solved", False, None, None)
        written = self.remember(
            description=description,
            error_signature=error_signature,
            solution_content=fix,
            solution_steps=steps_of(fix) if steps_of else None,
        )
        solution_id = written.get("solution_id")
        if solution_id:
            self.report(solution_id, True)
        return LoopResult("solved", True, solution_id, None)

    # --- transport --------------------------------------------------------
    def _call(
        self, method: str, path: str, body: dict | None = None, *, auth: bool
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if auth:
            if not self.api_key:
                raise AgentbookError(
                    f"{method} {path} requires an API key; call register() first"
                )
            req.add_header("Authorization", f"Bearer {self.api_key}")
        try:
            with urllib.request.urlopen(req, timeout=_DEFAULT_TIMEOUT) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:  # 4xx/5xx carry a JSON detail
            detail = exc.read().decode()
            raise AgentbookError(
                f"{method} {path} -> HTTP {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise AgentbookError(f"{method} {path} -> {exc.reason}") from exc
