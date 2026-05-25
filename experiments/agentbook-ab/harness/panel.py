"""Resolve the weak-model panel from OpenRouter's live model list.

We never hardcode a fixed slug set: we query GET /api/v1/models, keep models
whose prompt price is 0 (free), and intersect with a configured candidate list
so a slug that has been retired drops out automatically. The resolved panel is
cached with a timestamp for reproducibility.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
RUNS_V2 = ROOT / "runs_v2"
PANEL_CACHE = RUNS_V2 / "_panel.json"
MODELS_URL = "https://openrouter.ai/api/v1/models"

# Panel restricted (per eval owner) to these three free models and their paid
# fallbacks. The live filter below keeps those currently returned as free; the
# OpenRouterLLM paid fallback covers free unavailability (gemma upstream key
# expiry, gpt-oss upstream rate-limiting) by switching to the same model's paid
# endpoint, preserving model identity.
CANDIDATES = [
    "openai/gpt-oss-20b:free",
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
]


def model_slug(model_id: str) -> str:
    return model_id.replace("/", "_").replace(":", "_")


def _free_ids() -> set[str]:
    r = httpx.get(MODELS_URL, timeout=30.0)
    r.raise_for_status()
    data = r.json().get("data", [])
    free: set[str] = set()
    for m in data:
        pricing = m.get("pricing") or {}
        prompt = str(pricing.get("prompt", "")).strip()
        if prompt in ("0", "0.0", "0.00", "0e0"):
            free.add(m.get("id", ""))
    return free


def resolve_panel(
    candidates: list[str] | None = None, *, use_cache: bool = True
) -> list[str]:
    candidates = candidates or CANDIDATES
    if use_cache and PANEL_CACHE.exists():
        cached = json.loads(PANEL_CACHE.read_text())
        return cached["panel"]
    free = _free_ids()
    panel = [m for m in candidates if m in free]
    PANEL_CACHE.parent.mkdir(parents=True, exist_ok=True)
    PANEL_CACHE.write_text(
        json.dumps(
            {
                "resolved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "candidates": candidates,
                "free_total": len(free),
                "panel": panel,
            },
            indent=2,
        )
        + "\n"
    )
    return panel


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Resolve free-model panel")
    ap.add_argument("--refresh", action="store_true", help="ignore cache")
    args = ap.parse_args()
    panel = resolve_panel(use_cache=not args.refresh)
    print(f"panel ({len(panel)}):")
    for m in panel:
        print(f"  {m}  [{model_slug(m)}]")
