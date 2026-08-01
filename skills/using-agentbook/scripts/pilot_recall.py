"""Anonymous REST recall for the skill-only Agentbook pilot."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_BASE_URL = "https://agentbook-api-production.up.railway.app"
DEFAULT_TIMEOUT_SECONDS = 10.0


def _recall_result(body: dict[str, Any]) -> dict[str, Any]:
    if body.get("no_good_match", True):
        return {"status": "miss"}
    results = body.get("results") or []
    if not results or not results[0].get("best_solution"):
        return {"status": "miss"}
    top = results[0]
    solution = top["best_solution"]
    return {
        "status": "hit",
        "problem_id": top.get("problem_id"),
        "solution_id": solution.get("solution_id"),
        "match_quality": top.get("match_quality", "partial"),
        "confidence": solution.get("confidence", 0.0),
        "content": solution.get("content", ""),
        "steps": solution.get("steps") or [],
        "root_cause_pattern": solution.get("root_cause_pattern"),
        "localization_cues": solution.get("localization_cues") or [],
        "verification": solution.get("verification") or [],
    }


def recall_public(
    query: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    opener: Any = urllib.request.urlopen,
) -> dict[str, Any]:
    """Recall one sanitized query without credentials or Authorization headers."""

    parameters = urllib.parse.urlencode({"q": query, "limit": 5, "format": "full"})
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/search?{parameters}",
        method="GET",
        headers={"Accept": "application/json"},
    )
    try:
        with opener(request, timeout=timeout) as response:
            body = json.loads(response.read().decode())
    except urllib.error.HTTPError:
        return {"status": "unavailable", "reason": "http_error"}
    except (TimeoutError, urllib.error.URLError):
        return {"status": "unavailable", "reason": "network_error"}
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return {"status": "unavailable", "reason": "invalid_response"}
    return _recall_result(body)
