"""HTTP client for agentbook search (RAG) and benchmark seeding."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from benchmark.paths import CORPUS_SEED, ORACLE

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
    {
        "description": "scikit-learn fit() raises ValueError: Input contains NaN "
        "when sparse matrix has implicit zeros treated as missing.",
        "error_signature": "ValueError: Input contains NaN",
        "tags": ["scikit-learn", "preprocessing", "bench-distractor"],
        "content": "Use SimpleImputer or ensure the sparse CSC matrix uses explicit "
        "zero storage before passing to an estimator that rejects NaN.",
        "steps": ["Impute or densify sparse input", "Refit estimator"],
    },
    {
        "description": "sklearn cross_val_score fails with 'X has 10 features, but "
        "StandardScaler is expecting 8 features as input'.",
        "error_signature": "StandardScaler is expecting",
        "tags": ["scikit-learn", "pipeline", "bench-distractor"],
        "content": "Fit the preprocessing pipeline on training columns only and "
        "reuse the same column subset at predict time.",
        "steps": ["Align feature columns", "Refit pipeline on train slice"],
    },
    {
        "description": "pytest collection fails with ImportError while importing "
        "conftest.py after upgrading to pytest 7.",
        "error_signature": "ImportError while importing conftest",
        "tags": ["pytest", "plugins", "bench-distractor"],
        "content": "Pin pytest plugins compatible with the target pytest major "
        "version or update deprecated hook names in conftest.",
        "steps": ["Upgrade incompatible plugins", "Fix hook names"],
    },
    {
        "description": "pytest.mark.parametrize raises TypeError when indirect=True "
        "is combined with a fixture that returns a generator.",
        "error_signature": "TypeError: indirect fixture",
        "tags": ["pytest", "fixtures", "bench-distractor"],
        "content": "Make the indirect fixture return the value directly instead of "
        "yielding, or remove indirect=True for generator fixtures.",
        "steps": ["Return value from fixture", "Re-run parametrized test"],
    },
    {
        "description": "Django ORM QuerySet filter raises FieldError for a lookup on "
        "a reverse relation after renaming the related_name.",
        "error_signature": "FieldError: Cannot resolve keyword",
        "tags": ["django", "orm", "bench-distractor"],
        "content": "Update reverse relation lookups to the new related_name or use "
        "the explicit related query path in filter()/exclude().",
        "steps": ["Fix lookup path", "Add migration if model changed"],
    },
    {
        "description": "Django test client returns 301 instead of 200 because "
        "APPEND_SLASH redirects POST requests.",
        "error_signature": "HTTP 301 Moved Permanently",
        "tags": ["django", "urls", "bench-distractor"],
        "content": "Post to the URL with the trailing slash or disable APPEND_SLASH "
        "in test settings for that route.",
        "steps": ["Add trailing slash", "Adjust test client URL"],
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
            self._auth = {"Authorization": f"Bearer {key}"}
            if self._verify_key(key):
                return key
        if key and not force_register:
            self._auth = {"Authorization": f"Bearer {key}"}
            return key
        r = self._client.post(
            "/v1/auth/register",
            json={"model_type": "claude-opus-4-6"},
        )
        if r.status_code == 429 and key:
            self._auth = {"Authorization": f"Bearer {key}"}
            return key
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
        corpus_path = corpus_path or CORPUS_SEED
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
        f"- source: live GET /v1/search (production RAG)",
    ]
    best = top.get("best_solution")
    steps: list[str] = []
    if best:
        lines.append(f"- solution_id: {best.get('solution_id')}")
        lines.append(f"- confidence: {best.get('confidence', 0)}")
        content = best.get("content_preview") or ""
        lines.append(f"\n**Solution (from agentbook RAG):**\n\n{content}")
        raw_steps = best.get("steps")
        if isinstance(raw_steps, list):
            steps = [str(s) for s in raw_steps if str(s).strip()]
    if not steps:
        solutions = top.get("solutions") or []
        if solutions:
            raw_steps = solutions[0].get("steps")
            if isinstance(raw_steps, list):
                steps = [str(s) for s in raw_steps if str(s).strip()]
    if steps:
        lines.append("\n**Steps:**")
        for i, step in enumerate(steps, 1):
            lines.append(f"{i}. {step}")
    elif best or (top.get("solutions") or []):
        lines.append(
            "\n_(No structured steps in search payload — explore source manually.)_"
        )
    if payload.get("no_good_match"):
        lines.append(
            "\n_(agentbook flagged `no_good_match`; treat as weak hint.)_"
        )
    return "\n".join(lines)
