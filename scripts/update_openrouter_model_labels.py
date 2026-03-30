"""Apply OpenRouter-style model ids to agents and sync llm_model on solutions/research_cycles.

Run from repo root (loads DATABASE_URL from env or `.env`):

    uv run python scripts/update_openrouter_model_labels.py

Safe to run multiple times: idempotent for known legacy `model_type` values.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text


def _database_url() -> str:
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"].strip()
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("DATABASE_URL not set and not found in .env")


# Legacy / short labels -> OpenRouter ids (aligned with app/demo.py defaults)
_MODEL_TYPE_MAP: dict[str, str] = {
    "system": "anthropic/claude-sonnet-4.5",
    "claude-opus-4-5": "anthropic/claude-opus-4.6",
    "claude-sonnet-4-5": "anthropic/claude-sonnet-4.5",
    "gpt-4-turbo": "openai/gpt-5.4",
    "gemini-2.0-pro": "google/gemini-3-flash-preview",
    "claude-haiku-4-5": "anthropic/claude-haiku-4.5",
    # common test / shorthand
    "claude": "anthropic/claude-sonnet-4.5",
    "gemini": "google/gemini-3-flash-preview",
    "gpt-4": "openai/gpt-5.4",
    "cursor": "anthropic/claude-sonnet-4.5",
}


def main() -> None:
    url = _database_url()
    engine = create_engine(url)

    with engine.begin() as conn:
        # 1) Rewrite known legacy model_type values on agents
        for old, new in _MODEL_TYPE_MAP.items():
            r = conn.execute(
                text("UPDATE agents SET model_type = :new WHERE model_type = :old"),
                {"old": old, "new": new},
            )
            if r.rowcount:
                print(f"agents: {old!r} -> {new!r} ({r.rowcount} row(s))")

        # 2) System agent UUID: force display model if still placeholder
        r2 = conn.execute(
            text(
                """
                UPDATE agents
                SET model_type = :m
                WHERE agent_id = '00000000-0000-0000-0000-000000000001'
                  AND (model_type IS NULL OR model_type IN ('system', 'google-ai-studio/gemini-3.1-flash-lite-preview'))
                """
            ),
            {"m": "anthropic/claude-sonnet-4.5"},
        )
        if r2.rowcount:
            print(f"agents: system UUID model_type set ({r2.rowcount} row(s))")

        # 3) Sync solutions.llm_model from agents (overwrite to match current agent card)
        r3 = conn.execute(
            text(
                """
                UPDATE solutions AS s
                SET llm_model = a.model_type
                FROM agents AS a
                WHERE s.author_id = a.agent_id
                  AND a.model_type IS NOT NULL
                  AND btrim(a.model_type) <> ''
                """
            )
        )
        print(f"solutions: llm_model synced from agents ({r3.rowcount} row(s))")

        # 4) Sync research_cycles.llm_model from agents
        r4 = conn.execute(
            text(
                """
                UPDATE research_cycles AS rc
                SET llm_model = a.model_type
                FROM agents AS a
                WHERE rc.researcher_id = a.agent_id
                  AND a.model_type IS NOT NULL
                  AND btrim(a.model_type) <> ''
                """
            )
        )
        print(f"research_cycles: llm_model synced from agents ({r4.rowcount} row(s))")


if __name__ == "__main__":
    main()
