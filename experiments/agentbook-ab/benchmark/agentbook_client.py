"""HTTP client for agentbook search (RAG) and benchmark seeding."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from benchmark.paths import CORPUS_SEED, ORACLE

DEFAULT_BASE = "http://127.0.0.1:8078"
SEED_STATE = ORACLE / "seed_state_good.json"

# Same-domain (sympy) distractor memories. These describe *other* plausible
# sympy bugs whose surface (symbols, printers, sets, simplification) overlaps
# with the benchmark tasks, so retrieving the correct memory above them is a
# genuine test of the embedding/rerank stack -- not a unique-tag lookup. None of
# these correspond to a task in tasks/manifest.json.
DISTRACTORS = [
    {
        "description": "srepr of a Float loses precision: srepr(Float('1.1', 30)) "
        "drops the declared 30-digit precision when round-tripped through eval.",
        "error_signature": "Float precision lost in srepr",
        "tags": ["sympy", "printing", "Float", "bench-distractor"],
        "content": "ReprPrinter._print_Float must emit the precision argument so "
        "the repr round-trips; include the binary precision in the constructor call.",
        "steps": ["Open sympy/printing/repr.py", "Emit precision in _print_Float"],
    },
    {
        "description": "Integral of a Piecewise over a symbolic interval returns an "
        "unevaluated Integral instead of a Piecewise result.",
        "error_signature": "Integral not evaluated for Piecewise",
        "tags": ["sympy", "integrals", "Piecewise", "bench-distractor"],
        "content": "Dispatch piecewise integrands to piecewise_integrate so each "
        "branch is integrated under its own condition before recombining.",
        "steps": ["Detect Piecewise integrand", "Integrate branchwise"],
    },
    {
        "description": "simplify() fails to reduce trigonometric expression "
        "sin(x)**2 + cos(x)**2 to 1 when the symbol carries assumptions.",
        "error_signature": "trig identity not simplified",
        "tags": ["sympy", "simplify", "trigonometry", "bench-distractor"],
        "content": "Apply fu/trigsimp on the assumption-bearing atoms; the "
        "Pythagorean identity rewrite must run before generic cancellation.",
        "steps": ["Call trigsimp before cancel", "Preserve assumptions"],
    },
    {
        "description": "Matrix.rref() returns wrong pivot columns for a matrix with "
        "symbolic entries because zero-testing gives None.",
        "error_signature": "rref pivots incorrect with symbolic zero",
        "tags": ["sympy", "matrices", "rref", "bench-distractor"],
        "content": "Use the matrix's iszerofunc with simplify=True so symbolic "
        "entries that are structurally zero are detected during elimination.",
        "steps": ["Pass iszerofunc to rref", "Enable simplify in zero test"],
    },
    {
        "description": "lambdify with the numpy module mistranslates Max/Min to "
        "Python builtins, producing element-wise errors on arrays.",
        "error_signature": "lambdify Max numpy mismatch",
        "tags": ["sympy", "lambdify", "printer", "bench-distractor"],
        "content": "Map Max/Min to numpy.maximum/numpy.minimum in the numpy printer "
        "namespace so they broadcast over arrays.",
        "steps": ["Edit numpy printer mapping", "Map Max to numpy.maximum"],
    },
    {
        "description": "solve() drops a valid solution branch for an equation with a "
        "rational power because the radical check rejects it.",
        "error_signature": "solve missing radical branch",
        "tags": ["sympy", "solvers", "solve", "bench-distractor"],
        "content": "Relax the checksol radical verification to compare numerically "
        "within tolerance before discarding a candidate root.",
        "steps": ["Loosen checksol for radicals", "Re-verify candidates"],
    },
    {
        "description": "Poly division raises PolynomialError for multivariate input "
        "when the generators are passed in non-canonical order.",
        "error_signature": "PolynomialError: generators order",
        "tags": ["sympy", "polys", "Poly", "bench-distractor"],
        "content": "Canonicalise the generator tuple before constructing the dense "
        "representation so division aligns exponents consistently.",
        "steps": ["Sort generators", "Rebuild Poly with canonical gens"],
    },
    {
        "description": "FiniteSet intersection with an ImageSet returns EmptySet "
        "even though concrete members satisfy the image relation.",
        "error_signature": "intersection ImageSet empty",
        "tags": ["sympy", "sets", "intersection", "bench-distractor"],
        "content": "Add an intersection handler that substitutes finite members "
        "into the ImageSet lambda and keeps those that solve it.",
        "steps": ["Add handler in sets/handlers/intersection.py", "Test membership"],
    },
    {
        "description": "latex() renders a Derivative with the wrong bracket nesting "
        "for higher-order mixed partials.",
        "error_signature": "latex Derivative bracket",
        "tags": ["sympy", "printing", "latex", "bench-distractor"],
        "content": "Group the differentiation variables in LatexPrinter."
        "_print_Derivative so the order multiplicities render before the operand.",
        "steps": ["Edit sympy/printing/latex.py", "Fix _print_Derivative grouping"],
    },
    {
        "description": "parse_expr mishandles implicit multiplication next to a "
        "function call, parsing 2f(x) as a single name.",
        "error_signature": "parse implicit multiplication",
        "tags": ["sympy", "parsing", "parse", "bench-distractor"],
        "content": "Insert an implicit Mul token between a number and a following "
        "callable in the implicit-multiplication transformation.",
        "steps": ["Edit sympy_parser transformation", "Tokenise number*call"],
    },
    {
        "description": "Sum does not telescope a hypergeometric term and leaves the "
        "result unevaluated for a definite upper limit.",
        "error_signature": "Sum hypergeometric not evaluated",
        "tags": ["sympy", "concrete", "Sum", "bench-distractor"],
        "content": "Route hypergeometric summands through Gosper before falling "
        "back to the generic eval_sum path.",
        "steps": ["Detect hypergeometric term", "Apply Gosper summation"],
    },
    {
        "description": "Mod with a negative modulus returns a positive remainder, "
        "disagreeing with Python's % sign convention.",
        "error_signature": "Mod negative modulus sign",
        "tags": ["sympy", "core", "Mod", "bench-distractor"],
        "content": "Align Mod.eval with the divisor's sign so the remainder takes "
        "the sign of the modulus as Python's % does.",
        "steps": ["Edit sympy/core/mod.py", "Match remainder sign to modulus"],
    },
    {
        "description": "pycode printer emits math.factorial for a symbolic argument "
        "instead of guarding non-integer inputs.",
        "error_signature": "pycode factorial symbolic",
        "tags": ["sympy", "printing", "pycode", "bench-distractor"],
        "content": "Have the pycode printer fall back to a gamma-based expression "
        "when the factorial argument is not a concrete integer.",
        "steps": ["Edit sympy/printing/pycode.py", "Guard _print_factorial"],
    },
    {
        "description": "Quantum Dagger of a sum is not distributed over the "
        "addends, leaving Dagger(A + B) unexpanded.",
        "error_signature": "Dagger not distributed over Add",
        "tags": ["sympy", "physics.quantum", "dagger", "bench-distractor"],
        "content": "Implement Dagger over Add by mapping the adjoint across each "
        "argument so it distributes linearly.",
        "steps": ["Edit physics/quantum/dagger.py", "Distribute over Add"],
    },
    {
        "description": "geometry Point equality treats a 2D and a 3D point with the "
        "same first two coordinates as equal.",
        "error_signature": "Point equality dimension",
        "tags": ["sympy", "geometry", "Point", "bench-distractor"],
        "content": "Compare the ambient dimension in Point.__eq__ before comparing "
        "coordinates so differing dimensions are unequal.",
        "steps": ["Edit sympy/geometry/point.py", "Check dimension in __eq__"],
    },
    {
        "description": "units convert_to silently returns the original quantity "
        "when the target unit is dimensionally incompatible.",
        "error_signature": "convert_to incompatible units",
        "tags": ["sympy", "physics.units", "convert", "bench-distractor"],
        "content": "Raise (or return None) on a dimension mismatch in convert_to "
        "instead of returning the unconverted expression.",
        "steps": ["Edit physics/units/util.py", "Validate dimensions in convert_to"],
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
        if (
            skip_if_seeded
            and state.get("seeded")
            and state.get("corpus_path") == str(corpus_path.resolve())
        ):
            self.ensure_agent()
            return state

        self.ensure_agent(force_register=force_register or not state.get("api_key"))
        seeded: list[dict] = []
        for entry in corpus:
            iid = entry["instance_id"]
            # Semantic/domain tags only -- no per-task unique tag. A unique
            # `ab_task:{iid}` tag would make retrieval a trivial primary-key
            # lookup; recall is measured by retrieved problem_id identity instead.
            tags = [
                t for t in (entry.get("tags") or []) if not t.startswith("ab_task:")
            ]
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

    def seed_memories(
        self,
        memories_path: Path | str,
        *,
        include_distractors: bool = True,
        force_register: bool = True,
    ) -> dict:
        """Seed leakage-free peer-agent memories (good arm) + sympy distractors.

        Each memory entry: {instance_id, description, error_signature, tags,
        content, steps}; tags are semantic only (any ab_task:* is stripped).
        Records a problem_id -> instance_id map so retrieval recall is scored by
        identity, not a unique tag. force_register defaults True so a fresh
        in-memory (DEMO_MODE) database always gets a valid agent. Returns state.
        """
        memories_path = Path(memories_path)
        memories = json.loads(memories_path.read_text())
        state = self._load_state()
        self.ensure_agent(force_register=force_register or not state.get("api_key"))

        pid_to_iid: dict[str, str] = {}
        seeded: list[dict] = []
        for entry in memories:
            iid = entry["instance_id"]
            tags = [
                t for t in (entry.get("tags") or []) if not t.startswith("ab_task:")
            ][:20]
            pr = self._client.post(
                "/v1/problems",
                headers=self._auth,
                json={
                    "description": entry["description"],
                    "error_signature": entry.get("error_signature", ""),
                    "tags": tags,
                },
            )
            pr.raise_for_status()
            problem_id = pr.json()["problem_id"]
            sr = self._client.post(
                f"/v1/problems/{problem_id}/solutions",
                headers=self._auth,
                json={"content": entry["content"], "steps": entry.get("steps") or []},
            )
            sr.raise_for_status()
            pid_to_iid[problem_id] = iid
            seeded.append(
                {
                    "instance_id": iid,
                    "problem_id": problem_id,
                    "solution_id": sr.json()["solution_id"],
                }
            )

        distractor_pids: list[str] = []
        if include_distractors:
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
                distractor_pids.append(problem_id)

        state["memories_seeded"] = seeded
        state["pid_to_iid"] = pid_to_iid
        state["distractor_pids"] = distractor_pids
        state["memories_path"] = str(memories_path.resolve())
        state["mode"] = "memories"
        self._save_state(state)
        return state

    def search(
        self,
        query: str,
        *,
        error_log: str | None = None,
        limit: int = 3,
        authenticated: bool = False,
    ) -> dict[str, Any]:
        """Query GET /v1/search. Reads are public; default is anonymous (robust
        and within the 30/min anonymous budget). Pass authenticated=True only to
        use the higher 300/min agent tier."""
        headers: dict[str, str] = {}
        if authenticated:
            self.ensure_agent()
            headers = self._auth
        params: dict[str, Any] = {
            "q": query,
            "limit": limit,
            "format": "full",
            "include": "solutions",
        }
        if error_log:
            params["error_log"] = error_log
        r = self._client.get("/v1/search", headers=headers, params=params)
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
        "- source: live GET /v1/search (production RAG)",
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
        lines.append("\n_(agentbook flagged `no_good_match`; treat as weak hint.)_")
    return "\n".join(lines)
