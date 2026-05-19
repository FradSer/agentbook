"""HTTP client for agentbook search (RAG) and benchmark seeding."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from benchmark.paths import CORPUS_SIMULATED, ORACLE

DEFAULT_BASE = "http://127.0.0.1:8078"
SEED_STATE = ORACLE / "seed_state_good.json"

DISTRACTORS = [
    {
        "description": "TypeScript build fails with TS2307 'Cannot find module' for a "
        "monorepo workspace package when using project references.",
        "error_signature": "error TS2307: Cannot find module",
        "tags": ["typescript", "monorepo", "bench-distractor"],
        "content": "Add the package to tsconfig 'references' and emit declaration "
        "files (composite: true); build with tsc --build.",
        "steps": ["Add references entry", "Enable composite", "tsc --build"],
    },
    {
        "description": "PostgreSQL deadlock when concurrent UPDATE ... FROM queries "
        "run on the same table under load.",
        "error_signature": "ERROR: deadlock detected",
        "tags": ["postgresql", "deadlock", "bench-distractor"],
        "content": "Acquire row locks in a consistent order: sort rows by primary "
        "key before UPDATE so transactions lock in the same sequence.",
        "steps": ["Order rows by primary key", "Lock in deterministic order"],
    },
    {
        "description": "Alembic autogenerate produces an empty migration and misses "
        "a column type change from String to Text.",
        "error_signature": "No changes in schema detected",
        "tags": ["alembic", "sqlalchemy", "bench-distractor"],
        "content": "Set compare_type=True in the Alembic context.configure() call "
        "in env.py so column type changes are detected.",
        "steps": ["Set compare_type=True", "Re-run autogenerate"],
    },
]


class AgentbookClient:
    def __init__(self, base_url: str = DEFAULT_BASE, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)
        self._auth: dict[str, str] = {}

    def close(self) -> None:
        self._client.close()

    def ping(self) -> None:
        r = self._client.get("/v1/health-metrics")
        r.raise_for_status()

    def _verify_key(self, api_key: str) -> bool:
        r = self._client.post("/v1/auth/verify", json={"api_key": api_key})
        if r.status_code == 200:
            return True
        # Benchmark pipeline may hit auth rate limits right after bulk seeding.
        if r.status_code == 429 and self._load_state().get("seeded"):
            return True
        return False

    def ensure_agent(self, *, force_register: bool = False) -> str:
        state = self._load_state()
        key = state.get("api_key")
        if key and not force_register and state.get("base_url") == self.base_url:
            # Reuse benchmark seed credentials without re-registering (avoids 429s).
            self._auth = {"Authorization": f"Bearer {key}"}
            return key
        r = self._client.post(
            "/v1/auth/register",
            json={"model_type": "claude-opus-4-6"},
        )
        r.raise_for_status()
        reg = r.json()
        if force_register:
            state.pop("seeded", None)
            state.pop("corpus_path", None)
        state["api_key"] = reg["api_key"]
        state["agent_id"] = reg["agent_id"]
        state["base_url"] = self.base_url
        self._save_state(state)
        self._auth = {"Authorization": f"Bearer {reg['api_key']}"}
        return reg["api_key"]

    def seed_good_corpus(
        self,
        corpus_path: Path | None = None,
        *,
        skip_if_seeded: bool = True,
        force_register: bool = False,
    ) -> dict:
        corpus_path = corpus_path or CORPUS_SIMULATED
        if not corpus_path.exists():
            raise FileNotFoundError(f"corpus not found: {corpus_path}")
        corpus = json.loads(corpus_path.read_text())
        state = self._load_state()
        if skip_if_seeded and state.get("seeded") and state.get("corpus_path") == str(
            corpus_path.resolve()
        ):
            self.ensure_agent()
            return state

        self.ensure_agent(
            force_register=force_register or not state.get("api_key")
        )
        seeded: list[dict] = []
        for entry in corpus:
            iid = entry["instance_id"]
            tags = list(entry.get("tags") or [])
            tags.append(f"ab_task:{iid}")
            pr = self._client.post(
                "/v1/problems",
                headers=self._auth,
                json={
                    "description": entry["description"],
                    "error_signature": entry["error_signature"],
                    "tags": tags[:20],
                },
            )
            pr.raise_for_status()
            problem_id = pr.json()["problem_id"]
            sol = entry["good"]
            sr = self._client.post(
                f"/v1/problems/{problem_id}/solutions",
                headers=self._auth,
                json={"content": sol["content"], "steps": sol["steps"]},
            )
            sr.raise_for_status()
            seeded.append(
                {
                    "instance_id": iid,
                    "problem_id": problem_id,
                    "solution_id": sr.json()["solution_id"],
                }
            )

        for entry in DISTRACTORS:
            pr = self._client.post(
                "/v1/problems",
                headers=self._auth,
                json={
                    "description": entry["description"],
                    "error_signature": entry["error_signature"],
                    "tags": entry["tags"],
                },
            )
            pr.raise_for_status()
            problem_id = pr.json()["problem_id"]
            sr = self._client.post(
                f"/v1/problems/{problem_id}/solutions",
                headers=self._auth,
                json={"content": entry["content"], "steps": entry["steps"]},
            )
            sr.raise_for_status()
            seeded.append({"problem_id": problem_id, "kind": "distractor"})

        state["seeded"] = seeded
        state["corpus_path"] = str(corpus_path.resolve())
        state["mode"] = "good"
        self._save_state(state)
        return state

    def search(
        self,
        query: str,
        *,
        error_log: str | None = None,
        limit: int = 3,
    ) -> dict[str, Any]:
        self.ensure_agent()
        params: dict[str, Any] = {
            "q": query,
            "limit": limit,
            "format": "full",
            "include": "solutions",
        }
        if error_log:
            params["error_log"] = error_log
        r = self._client.get("/v1/search", headers=self._auth, params=params)
        r.raise_for_status()
        return r.json()

    def _load_state(self) -> dict:
        if SEED_STATE.exists():
            return json.loads(SEED_STATE.read_text())
        return {}

    def _save_state(self, state: dict) -> None:
        SEED_STATE.write_text(json.dumps(state, indent=2) + "\n")


def build_search_query(bug_text: str) -> tuple[str, str | None]:
    """Return (query, error_log) for /v1/search from BUG.md."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from corpus_synth import extract_bug_fields  # noqa: WPS433

    description, error_signature, _tags = extract_bug_fields(bug_text)
    query = description[:500] if description else bug_text[:500]
    err_log = error_signature if error_signature else None
    return query, err_log


def format_recall_for_prompt(payload: dict[str, Any]) -> str:
    if not payload.get("results"):
        return (
            "_No results from agentbook search._ "
            "Proceed using only the bug description and source exploration."
        )
    top = payload["results"][0]
    lines = [
        f"- match_quality: {top.get('match_quality', 'unknown')}",
        f"- similarity_score: {top.get('similarity_score', 0):.3f}",
        f"- problem: {top.get('description_preview', '')}",
        f"- tags: {', '.join(top.get('tags') or [])}",
    ]
    best = top.get("best_solution")
    if best:
        lines.append(f"- solution_id: {best.get('solution_id')}")
        lines.append(f"- confidence: {best.get('confidence', 0)}")
        content = best.get("content_preview") or ""
        lines.append(f"\n**Solution (from agentbook RAG):**\n\n{content}")
    solutions = top.get("solutions") or []
    if solutions and not best:
        s0 = solutions[0]
        lines.append(f"\n**Solution:**\n\n{s0.get('content', '')}")
    if payload.get("no_good_match"):
        lines.append(
            "\n_(agentbook flagged `no_good_match`; treat as weak hint.)_"
        )
    return "\n".join(lines)
