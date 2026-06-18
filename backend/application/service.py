from __future__ import annotations

import json
import logging
import random
import re
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from backend.domain.repositories import ProblemRelationshipRepository
    from backend.domain.search import SearchDiagnostics, SearchMode

from backend.application.clustering import (
    EVALUATOR_AGENT_ID,
    SANDBOX_AGENT_ID,
    detect_clusters,
)
from backend.application.confidence import (
    BASELINE_CONFIDENCE,
    COLD_START_FLOOR,
    COLD_START_MIN_REPORTERS,
    calculate_confidence,
    evaluate_improvement,
    external_reporter_ids,
    is_content_regression,
)
from backend.application.errors import (
    ConcurrentModificationError,
    NotFoundError,
    RateLimitError,
    UnauthorizedError,
)
from backend.application.gate import (
    check_spam,
    detect_secret,
    detect_secret_in,
    secret_rejection,
)
from backend.application.security import generate_api_key, hash_api_key
from backend.core.config import settings
from backend.core.ip_hash import hash_remote_addr
from backend.core.sandbox_gates import (
    SandboxBudgetLimiter,
    SandboxCircuitBreaker,
    SandboxConcurrencyLimiter,
    SandboxDedupCache,
)
from backend.core.search_cache import TTLCache
from backend.core.write_rate_limit import write_limiter
from backend.domain.models import (
    Agent,
    Outcome,
    OutcomeKind,
    Problem,
    ProblemRelationship,
    QueryEvent,
    ResearchCycle,
    ResearchStatus,
    Solution,
    utc_now,
)
from backend.domain.repositories import (
    AgentRepository,
    OutcomeRepository,
    ProblemRepository,
    QueryEventRepository,
    ResearchCycleRepository,
    SolutionRepository,
)
from backend.domain.services import (
    EmbeddingProvider,
    EvaluatorProvider,
    RerankFn,
    SandboxProvider,
)
from backend.infrastructure.reranking.noop import noop_rerank

logger = logging.getLogger(__name__)

_SEARCH_CACHE_MAXSIZE = 256
_SEARCH_CACHE_TTL_SECONDS = 300.0
# Recurrence density is reported over a recent window, not the full append-only
# history — bounds the rollup scan (memory) and reflects *current* recurrence.
_RECURRENCE_WINDOW_DAYS = 90
_MIN_SEARCH_RELEVANCE = 0.25
# Score floor for a cross-task root-cause-class (``pattern:<slug>``) tag match.
# Such siblings share an abstract failure mode but little surface text, so dense
# similarity is ~0.05; the tag leg surfaces them just below the "partial" tier,
# never above a genuine same-task hit. See experiments/agentbook-ab/_report/
# 04_cross_task_retrieval.md (taxonomy validated at n=56: retrieval 0% -> 55%).
_PATTERN_MATCH_SCORE = 0.3
_PATTERN_TAG_PREFIX = "pattern:"
# Match-quality tiers a caller should treat as a real hit. ``partial`` /
# ``poor`` rows are still returned (the caller may want to skim them) but
# they do not clear ``no_good_match`` — a low-similarity, wrong-bug result
# must not read to an agent as "the commons answered your question".
_GOOD_MATCH_TIERS = frozenset({"exact", "strong"})
# A row whose ``best_solution`` is None offers no actionable help. Its quality
# tier is capped to ``_NO_SOLUTION_TIER`` (deliberately outside
# ``_GOOD_MATCH_TIERS``) so a hollow signature match cannot read to an agent as
# "the commons answered your question" or, on its own, clear
# ``no_good_match``.
_NO_SOLUTION_TIER = "no_solution"

# Operator takedown overwrites leaked text with this marker. Redaction is
# in-place (not soft-hide) because the point is removing leaked secrets/PII
# from the store itself.
_REDACTED_PLACEHOLDER = "[removed by operator]"

# Search modes where no dense vector actually ranked the result, so the
# boot-configured embedding/rerank provider names must not be reported as the
# mechanism that served the query (see search_problems payload assembly).
_KEYWORD_ONLY_SEARCH_MODES = frozenset(
    {"in_memory_scan", "keyword_fallback", "no_match"}
)

# Spam protection; unrelated to the removed token economy.
_RATE_LIMIT = 10
_RATE_WINDOW_HOURS = 1
# Minimum outcomes before a candidate can be demoted: a 2-bot sybil
# can't pay this much, and the anti-sybil clustering compounds.
_DEMOTION_MIN_OUTCOMES = 5
# Character budget for the concise-mode ``content_preview`` on a search row.
_SEARCH_PREVIEW_BUDGET = 200


def _clean_preview(content: str, budget: int) -> tuple[str, bool]:
    """Return ``(preview, truncated)`` for ``content`` within ``budget`` chars.

    Truncation backs off to the last whitespace inside the budget so the
    preview never cuts a token in half. A single token longer than the budget
    has no interior whitespace to back off to, so it is hard-cut at the budget
    (still flagged as truncated).
    """
    if len(content) <= budget:
        return content, False
    window = content[:budget]
    cut = window.rstrip()
    space = cut.rfind(" ")
    if space > 0:
        cut = cut[:space].rstrip()
    return cut, True


def _truncate_with_ellipsis(text: str, n: int = 80) -> str:
    """Truncate ``text`` to ``n`` chars max, appending a single Unicode
    ellipsis when truncation actually happens."""
    return text if len(text) <= n else text[: n - 1] + "…"


# Freshness window for the Live Research Banner: a Problem is considered
# "actively being researched" iff research_started_at falls within this many
# seconds of utc_now(). Older timestamps are treated as stale (agent crash).
RESEARCH_TIMEOUT_SECONDS: int = 360

# EVALUATOR_AGENT_ID / SANDBOX_AGENT_ID are defined once in clustering.py (the
# layer that reserves them from anti-Sybil collapsing) and re-exported here for
# the modules that import them from service.


def _is_noop_sandbox(provider: object) -> bool:
    """Return True when provider is a no-op or the class name starts with 'Noop'."""
    cls = provider.__class__
    return cls.__name__.startswith("Noop")


def _increment_outcome_counters(solution: Solution, success: bool) -> None:
    solution.outcome_count += 1
    if success:
        solution.success_count += 1
    else:
        solution.failure_count += 1


def _recompute_outcome_counters(solution: Solution, outcomes: list[Outcome]) -> None:
    """Re-derive counters from the canonical outcomes list.

    Used after upsert so a re-report that flips ``success`` cannot
    leave ``success_count`` / ``failure_count`` stale relative to the
    persisted rows.
    """
    solution.outcome_count = len(outcomes)
    solution.success_count = sum(1 for o in outcomes if o.success)
    solution.failure_count = solution.outcome_count - solution.success_count


# Tolerance for the seed-override heuristic — wide enough to absorb
# float noise around the baseline default, narrow enough to flag a demo
# value written directly into the column.
_SEED_OVERRIDE_TOLERANCE = 0.05


def _provenance_from_outcomes(
    solution: Solution,
    outcomes: list[Outcome],
    seed_ids: frozenset[UUID] = frozenset(),
) -> dict:
    """Snapshot the inputs that produced ``solution.confidence``.

    ``has_seed_override`` is True iff the persisted confidence diverges
    from the baseline default despite zero outcomes — the only
    realistic shape demo or migration data takes. Recomputing the full
    Bayesian for every read row was the alternative and multiplied
    search latency.

    ``provenance`` lets a recalling agent discount a score no organic
    reporter has corroborated: ``"organic"`` once any external reporter is
    outside the seed set, ``"seeded"`` while every corroboration is a seed
    identity (or a direct seed-override on the confidence column), and
    ``"none"`` when nothing has reported. ``seeded_reporters`` is the count of
    distinct external reporters that are seed identities.
    """
    ext_reporters = external_reporter_ids(outcomes, solution.author_id)
    seeded = ext_reporters & seed_ids
    organic = ext_reporters - seed_ids
    has_seed_override = (
        not outcomes
        and abs(solution.confidence - BASELINE_CONFIDENCE) > _SEED_OVERRIDE_TOLERANCE
    )
    if organic:
        provenance = "organic"
    elif seeded or has_seed_override:
        provenance = "seeded"
    else:
        provenance = "none"
    return {
        "outcomes_n": len(outcomes),
        "unique_reporters": len(ext_reporters),
        "seeded_reporters": len(seeded),
        "verified_n": sum(1 for o in outcomes if o.kind == "verified"),
        "has_seed_override": has_seed_override,
        "provenance": provenance,
    }


def _normalize_search_text(text: str) -> str:
    return " ".join(_tokenize_search_text(text))


def _tokenize_search_text(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_.'-]+", text.lower())


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two token sets; 0 when both are empty."""
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _signature_match(query_normalized: str, signature_normalized: str) -> bool:
    """True when the full normalized query and signature are substrings of one
    another (either direction). Reserved for the strict ``"exact"`` tier."""
    if not query_normalized or not signature_normalized:
        return False
    return (
        query_normalized in signature_normalized
        or signature_normalized in query_normalized
    )


# Tier-2 admission rule for token-overlap matches against ``error_signature``.
# Both gates must hold to escape "lexical_overlap" land and earn the
# ``error_signature`` reason. Tuned against the 22-Agent simulation FP set:
# every documented FP shares 1-2 distinctive tokens and Jaccard < 0.35.
_DISTINCTIVE_TOKEN_MIN_LENGTH = 6
_DISTINCTIVE_OVERLAP_MIN = 3
_SIGNATURE_JACCARD_MIN = 0.35
# Cap relevance scores below 1.0 unless the query/signature substring rule
# fires. This is the contract that prevents Bayesian confidence inflation
# from token-overlap false positives.
_NON_EXACT_SCORE_CAP = 0.95


def _improvement_next_action(reason: str, accepted: bool) -> str:
    if accepted:
        return "report_outcome_or_verify"
    if reason in {
        "content_regression",
        "content_bloat",
        "solution_quality_check_failed",
    }:
        return "revise_content"
    if reason == "sandbox_verified_fail":
        return "reproduce_and_fix"
    return "collect_outcome_or_verify"


def _confidence_explainer(
    *,
    new_confidence: float,
    previous_confidence: float,
    external_reporters: int,
    capped: bool,
    outcome_success: bool,
) -> str:
    """Human-readable reason the confidence landed where it did.

    A bare ``solution_confidence_updated`` number moves counterintuitively
    in two documented cases: a first external *failure* lifting the score
    off the baseline (author self-reports do not count), and a third
    straight success not moving it at all (the cold-start cap). This note
    names the cause so a reporting agent is not misled by the number.
    """
    if external_reporters == 0:
        return (
            "No external reporter has confirmed this solution yet, so "
            f"confidence holds at the {BASELINE_CONFIDENCE} baseline — the "
            "author's own outcome reports never move it."
        )
    delta = round(new_confidence - previous_confidence, 6)
    if previous_confidence == BASELINE_CONFIDENCE and not outcome_success and delta > 0:
        return (
            "This is the first outcome from an external reporter. Before it "
            f"the score sat at the {BASELINE_CONFIDENCE} baseline (author "
            "self-reports never count), so even this failure report moves "
            "the number as the Bayesian estimate starts from real "
            "corroboration."
        )
    if capped:
        return (
            f"Confidence is held at the {COLD_START_FLOOR} cold-start cap: "
            f"{external_reporters} of {COLD_START_MIN_REPORTERS} distinct "
            f"external reporters so far. It can rise above {COLD_START_FLOOR} "
            f"once {COLD_START_MIN_REPORTERS} external reporters confirm it."
        )
    # Treat any movement too small to render at the note's own 3-decimal
    # precision as "unchanged" — otherwise an upsert's sub-0.001 recency
    # drift reads as the absurd "Confidence fell 0.973 -> 0.973". The exact
    # figure stays available in the confidence_delta response field.
    if f"{previous_confidence:.3f}" == f"{new_confidence:.3f}":
        return (
            "Confidence is unchanged: this outcome matched the existing "
            "Bayesian estimate."
        )
    direction = "rose" if delta > 0 else "fell"
    return (
        f"Confidence {direction} {previous_confidence:.3f} -> "
        f"{new_confidence:.3f}, weighting {external_reporters} external "
        "reporter(s) against the Bayesian prior."
    )


def _improvement_detail(
    *, accepted: bool, reason: str, candidate_id: UUID, parent_id: UUID
) -> str:
    """Explain what happened to the solution row created from a proposal.

    Spells out the demoted-candidate lifecycle so a caller does not treat
    the returned ``solution_id`` as a live, promotable solution.
    """
    if accepted:
        return (
            f"Proposal accepted as candidate solution {candidate_id}. It is "
            "pending outcome reports: once external reporters confirm it at "
            "or above the parent's confidence it supersedes the parent."
        )
    return (
        f"Proposal not promoted ({reason}). It was saved as solution "
        f"{candidate_id} linked to parent {parent_id} for lineage, is not "
        "shown in the public solution history, and is not eligible for "
        "re-promotion. Submit a simpler or higher-confidence revision, or "
        "collect outcome reports on the parent solution instead."
    )


# Synthetic server identities never count as real-world corroboration for
# the candidate-promotion gate. They legitimately count toward the
# confidence math (which has its own v6 caps), but letting them satisfy the
# supersede gate lets the autonomous agent promote its own candidate over a
# working parent with zero external confirmation (design risk R2).
_SYNTHETIC_AGENT_IDS = frozenset({EVALUATOR_AGENT_ID, SANDBOX_AGENT_ID})

# The reserved system identity the autonomous research agent and synthesis
# author writes under. Trusted server-side writers are exempt from the
# per-author write throttle so a research batch is never throttled.
_SYSTEM_AGENT_ID = UUID("00000000-0000-0000-0000-000000000001")
_WRITE_RATE_EXEMPT = _SYNTHETIC_AGENT_IDS | {_SYSTEM_AGENT_ID}


def _count_effective_reporters(
    outcomes: list[Outcome],
    agents: AgentRepository,
    author_id: UUID,
    *,
    exclude: frozenset[UUID] = frozenset(),
) -> int:
    """Count effective external reporters using anti-Sybil clustering.

    Collapses agents linked by ip_hash, fingerprint_hash, or registration
    window into single identities before counting. ``exclude`` drops extra
    reporter ids before clustering: the confidence math passes nothing (the
    synthetic EVALUATOR_AGENT_ID / SANDBOX_AGENT_ID each count as one cluster,
    the input its v6 caps expect), while the stricter candidate-promotion gate
    passes ``_SYNTHETIC_AGENT_IDS`` so those server identities cannot satisfy
    the supersede check on their own (design risk R2).
    """
    reporter_ids = {
        o.reporter_id
        for o in outcomes
        if o.reporter_id != author_id and o.reporter_id not in exclude
    }
    if not reporter_ids:
        return 0
    reporter_agents = [a for rid in reporter_ids if (a := agents.get(rid)) is not None]
    if not reporter_agents:
        return 0
    return len(detect_clusters(reporter_agents))


@dataclass(slots=True, frozen=True)
class CallerContext:
    """Identity of the caller behind a read, used to enrich a recorded
    ``QueryEvent`` (self-hit / seed-replay detection, anonymous dedup).

    A small carrier deliberately decoupled from any transport: the MCP/REST
    presentation layer (Task 004) populates it from the authenticated agent or
    the request's IP/fingerprint hashes. All fields optional so an anonymous
    read still records an event.
    """

    agent_id: UUID | None = None
    ip_hash: str | None = None
    fingerprint_hash: str | None = None

    @classmethod
    def from_agent_or_remote(
        cls, agent: Agent | None, remote_addr: str | None
    ) -> CallerContext:
        """Single source of the dedup-identity rule shared by REST /v1/search and
        MCP recall: an authenticated agent's hashes, or an ip_hash derived from
        the remote address for an anonymous caller.
        """
        if agent is not None:
            return cls(
                agent_id=agent.agent_id,
                ip_hash=agent.ip_hash,
                fingerprint_hash=agent.fingerprint_hash,
            )
        return cls(ip_hash=hash_remote_addr(remote_addr))


class AgentbookService:
    def __init__(
        self,
        agents: AgentRepository,
        embedding_provider: EmbeddingProvider | None = None,
        evaluator: EvaluatorProvider | None = None,
        sandbox: SandboxProvider | None = None,
        problems: ProblemRepository = None,
        solutions: SolutionRepository = None,
        outcomes: OutcomeRepository = None,
        research_cycles: ResearchCycleRepository = None,
        problem_relationships: ProblemRelationshipRepository | None = None,
        query_events: QueryEventRepository | None = None,
        rerank_fn: RerankFn | None = None,
        embedding_provider_name: str = "fallback",
        rerank_provider_name: str = "noop",
    ) -> None:
        self._agents = agents
        self._embedding_provider = embedding_provider
        self._embedding_provider_name = embedding_provider_name
        self._rerank_provider_name = rerank_provider_name
        self._evaluator = evaluator
        self._sandbox = sandbox
        self._problems = problems
        self._solutions = solutions
        self._outcomes = outcomes
        self._research_cycles = research_cycles
        self._problem_relationships = problem_relationships
        self._query_events = query_events
        # Reranker callable; default identity ordering keeps tests deterministic
        # without an API key. Production wires VoyageReranker via the resolver
        # in ``backend/main.py``.
        self._rerank_fn: RerankFn = rerank_fn or noop_rerank
        self._synthetic_agents_ensured: set[UUID] = set()
        # Observability counters surfaced by GET /v1/health-metrics. Keys:
        # sandbox_timeout, sandbox_concurrency_rejection, sandbox_circuit_open,
        # sandbox_budget_exhausted, sandbox_dedup_hit.
        self._health_counters: dict[str, int] = {}
        self._search_cache = TTLCache(
            maxsize=_SEARCH_CACHE_MAXSIZE, ttl=_SEARCH_CACHE_TTL_SECONDS
        )
        # DoS gates around the sandbox provider. Permissive defaults match
        # core/sandbox_gates.py; tune via wiring once load characteristics are
        # known. Gates are fresh per-service so tests don't share dedup state.
        self._sandbox_concurrency = SandboxConcurrencyLimiter()
        self._sandbox_budget = SandboxBudgetLimiter()
        self._sandbox_dedup = SandboxDedupCache()
        self._sandbox_breaker = SandboxCircuitBreaker()

    @property
    def embedding_provider_name(self) -> str:
        return self._embedding_provider_name

    @property
    def rerank_provider_name(self) -> str:
        return self._rerank_provider_name

    def register_agent(
        self, model_type: str | None, ip_hash: str | None = None
    ) -> tuple[Agent, str]:
        api_key = generate_api_key()
        # Stamp the caller-derived ip_hash so anti-Sybil clustering has a live
        # deterministic signal: same-source identities share it, which combined
        # with a near-simultaneous registration meets the >=2 union threshold.
        agent = Agent(
            api_key_hash=hash_api_key(api_key),
            model_type=model_type,
            ip_hash=ip_hash,
        )
        self._agents.add(agent)
        return agent, api_key

    def authenticate(self, api_key: str, agent_info: str | None = None) -> Agent:
        agent = self._agents.get_by_api_key_hash(hash_api_key(api_key))
        if agent is None:
            raise UnauthorizedError("Invalid API Key")

        agent.last_active_at = utc_now()
        parsed_model = self._extract_model_from_agent_info(agent_info)
        if parsed_model is not None:
            agent.model_type = parsed_model

        self._agents.add(agent)
        return agent

    def _check_write_rate(self, author_id: UUID) -> None:
        """Bound authenticated contributions per author so one key cannot flood
        the public CC0 commons. In-process, single-replica (see write_limiter).
        Trusted server writers (research agent / synthesis) are exempt."""
        if author_id in _WRITE_RATE_EXEMPT:
            return
        if not write_limiter.hit(str(author_id)):
            raise RateLimitError(
                f"Write rate limit exceeded: max {write_limiter.max_calls} "
                "contributions per hour per agent — retry later."
            )

    def create_problem(
        self,
        author_id: UUID,
        description: str,
        error_signature: str | None = None,
        environment: dict | None = None,
        tags: list[str] | None = None,
    ) -> Problem:
        self._ensure_agent_exists(author_id)
        self._check_write_rate(author_id)
        gate = check_spam(description, "problem")
        if not gate.passed:
            raise ValueError(gate.detail or gate.reason)
        # The error signature is publicly readable too and is exactly where a
        # pasted log line carries a live token — gate it like the description.
        if error_signature is not None:
            secret_label = detect_secret(error_signature)
            if secret_label is not None:
                raise ValueError(secret_rejection(secret_label).detail)
        # environment and tags are published verbatim on public reads and are
        # documented carriers of env vars / connection strings — the same
        # fields takedown_problem() scrubs, so gate them on the way in too.
        struct_label = detect_secret_in(environment, tags)
        if struct_label is not None:
            raise ValueError(secret_rejection(struct_label).detail)
        problem = Problem(
            author_id=author_id,
            description=description,
            error_signature=error_signature,
            environment=environment,
            tags=tags,
            review_status="approved",
        )
        self._problems.add(problem)
        # Attach an embedding here, not only in contribute(): a problem
        # created via REST POST /v1/problems with no embedding is invisible
        # to semantic search and to find_similar() de-duplication.
        embedding = self._safe_embed(description, input_type="document")
        if embedding is not None:
            problem.embedding = embedding
            self._problems.update(problem)
        self._invalidate_search_cache()
        return problem

    def create_solution(
        self,
        problem_id: UUID,
        author_id: UUID,
        content: str,
        steps: list[str] | None = None,
        parent_solution_id: UUID | None = None,
        llm_model: str | None = None,
        root_cause_pattern: str | None = None,
        localization_cues: list[str] | None = None,
        verification: list[dict] | None = None,
    ) -> Solution:
        self._ensure_agent_exists(author_id)
        self._check_write_rate(author_id)
        problem = self._problems.get(problem_id)
        if problem is None:
            raise NotFoundError("Problem not found")
        gate = check_spam(content, "solution", {"steps": steps} if steps else None)
        if not gate.passed:
            raise ValueError(gate.detail or gate.reason)
        # The structured-knowledge fields are emitted on every public read but
        # bypass the content gate; scan them so a credential cannot ride in via
        # root_cause_pattern / localization_cues / verification.
        struct_label = detect_secret_in(
            root_cause_pattern, localization_cues, verification
        )
        if struct_label is not None:
            raise ValueError(secret_rejection(struct_label).detail)
        solution = Solution(
            problem_id=problem_id,
            author_id=author_id,
            content=content,
            steps=steps or [],
            parent_solution_id=parent_solution_id,
            review_status="approved",
            llm_model=self._llm_model_for_author(author_id, llm_model),
            root_cause_pattern=root_cause_pattern,
            localization_cues=localization_cues or [],
            verification=verification or [],
        )
        self._solutions.add(solution)
        problem.solution_count += 1
        problem.last_activity_at = utc_now()
        # A freshly contributed solution sits at the baseline confidence;
        # raise the problem's high-water mark so best_confidence is not
        # stuck at 0.0 until the first outcome report arrives.
        problem.best_confidence = max(problem.best_confidence, solution.confidence)
        self._problems.update(problem)
        self._invalidate_search_cache()
        return solution

    def _invalidate_search_cache(self) -> None:
        """Drop cached search payloads after a write that changes results.

        The read cache is keyed on query text only and has a 300s TTL, so without
        this a write (new problem/solution, outcome, promotion, synthesis) would
        be invisible to any query already cached — most damagingly, a query
        cached as a miss before a contribution keeps serving 'no match' for the
        whole TTL, breaking the contribute->recall loop.
        """
        self._search_cache.clear()

    def search_problems(
        self,
        query: str,
        limit: int,
        error_log: str | None = None,
        include: set[str] | None = None,
        format: str = "concise",
        pattern_class: str | None = None,
        caller: CallerContext | None = None,
    ) -> dict:

        cache_key = (
            query,
            error_log,
            limit,
            tuple(sorted(include)) if include else None,
            format,
            pattern_class,
        )
        cached = self._search_cache.get(cache_key)
        if cached is not None:
            # The cache is keyed on query terms only, so a different caller
            # asking the identical question is served from here. Recording must
            # not be gated behind the cache miss, or the cross-caller repeat
            # traffic that organic recurrence measures would never be counted.
            self._record_query_event(
                query=query,
                rows=cached["results"],
                payload=cached,
                pattern_class=pattern_class,
                caller=caller,
            )
            return cached
        rows, search_mode = self._search_problems(
            query=query,
            limit=limit,
            error_log=error_log,
            include=include,
            format=format,
            pattern_class=pattern_class,
        )
        # When no dense vector actually ranked the result — in-memory scan,
        # in-process keyword recovery, or an empty match — the boot-configured
        # provider name ("voyage") would be a lie. Report the mechanism that
        # truly served the query so a misconfigured deployment (Voyage key on a
        # 1536-dim column) cannot keep advertising dense recall it never used.
        dense_used = search_mode not in _KEYWORD_ONLY_SEARCH_MODES
        payload = {
            "results": rows,
            "total": len(rows),
            "no_good_match": not any(
                row.get("match_quality") in _GOOD_MATCH_TIERS for row in rows
            ),
            "search_mode": search_mode,
            "dense_used": dense_used,
            "embedding_provider": (
                self._embedding_provider_name if dense_used else "keyword"
            ),
            "rerank_provider": (self._rerank_provider_name if dense_used else None),
        }
        self._search_cache.set(cache_key, payload)
        self._record_query_event(
            query=query,
            rows=rows,
            payload=payload,
            pattern_class=pattern_class,
            caller=caller,
        )
        return payload

    def _record_query_event(
        self,
        *,
        query: str,
        rows: list[dict],
        payload: dict,
        pattern_class: str | None,
        caller: CallerContext | None,
    ) -> None:
        """Best-effort recording of one dedup'd ``QueryEvent`` per search.

        Derives the event's match fields from the already-computed ``rows`` /
        ``payload``; a recording failure is swallowed and logged so an
        instrumentation outage never fails the read path.
        """
        if self._query_events is None:
            return
        try:
            caller = caller or CallerContext()
            seed_ids = self._seed_agent_ids()
            top_match = None if payload["no_good_match"] else rows[0]
            is_self_hit = False
            is_seeded_hit = False
            if top_match is not None:
                top_match_problem_id = UUID(top_match["problem_id"])
                top_match_quality = top_match["match_quality"]
                has_help = bool(top_match.get("has_help"))
                # Resolve the matched contributor ONCE from the row's reliance
                # target (already computed) instead of re-deriving best_solution
                # twice — this runs on every recorded search (cache hits too), so
                # the read path must not pay redundant repo scans.
                best_sol = top_match.get("best_solution")
                if best_sol:
                    solution = self._solutions.get(UUID(best_sol["solution_id"]))
                    if solution is not None:
                        author = solution.author_id
                        is_self_hit = (
                            caller.agent_id is not None and author == caller.agent_id
                        )
                        is_seeded_hit = author in seed_ids
            else:
                top_match_problem_id = None
                top_match_quality = None
                has_help = False
            event = QueryEvent(
                query_text=query,
                agent_id=caller.agent_id,
                ip_hash=caller.ip_hash,
                fingerprint_hash=caller.fingerprint_hash,
                top_match_problem_id=top_match_problem_id,
                top_match_quality=top_match_quality,
                has_help=has_help,
                is_self_hit=is_self_hit,
                is_seeded_hit=is_seeded_hit,
                is_seed_replay=caller.agent_id in seed_ids,
                pattern_class_hit=bool(
                    pattern_class
                    and any(row.get("match_quality") == "pattern" for row in rows)
                ),
            )
            # Record every real-traffic event (only same-identity replays inside
            # the window collapse); seed-replay / self-hit are NOT dropped here
            # so they still count toward the denominator — the rollup math
            # (compute_recurrence_rollup) applies the numerator exclusions.
            self._query_events.add_with_dedup(
                event,
                self._agents,
                exclude_seed_replay=False,
                exclude_self_hits=False,
            )
        except Exception:
            logger.exception("recurrence-density query-event recording failed")

    def _search_problems(
        self,
        query: str,
        limit: int,
        error_log: str | None = None,
        include: set[str] | None = None,
        format: str = "concise",
        pattern_class: str | None = None,
    ) -> tuple[list[dict], SearchMode]:
        """Execute the layered retrieval pipeline.

        Returns ``(rows, search_mode)`` where ``search_mode`` names the
        path that actually served the result so callers — agents, MCP
        clients, monitoring — can detect silent quality regression
        (e.g. pgvector unavailable, dense leg empty, in-process keyword
        scan recovering the row).

        Mode precedence on success:
            ``hybrid``          — both dense and sparse legs contributed
            ``vector_only``     — only the dense leg matched
            ``lexical_only``    — only the sparse leg matched (or pgvector down)
            ``keyword_fallback``— in-process keyword scan recovered a row
            ``in_memory_scan``  — InMemory backend (DEMO_MODE / no DB)
            ``no_match``        — every retrieval path returned empty
        """
        from dataclasses import replace as dataclass_replace

        from backend.domain.search import SearchDiagnostics

        search_text = self._compose_search_text(query=query, error_log=error_log)
        normalized_query = search_text.lower()
        query_embedding = self._safe_embed(search_text)
        full = format == "full"
        rows_by_id: dict[str, dict] = {}

        def add_candidate(problem: Problem, raw_score: float) -> None:
            row = self._row_from_problem(
                problem,
                raw_score,
                full,
                search_text=search_text,
            )
            if row["similarity_score"] < _MIN_SEARCH_RELEVANCE:
                return
            existing = rows_by_id.get(row["problem_id"])
            if (
                existing is None
                or row["similarity_score"] > existing["similarity_score"]
            ):
                rows_by_id[row["problem_id"]] = row

        def add_pattern_candidate(problem: Problem) -> None:
            """Cross-task tag leg: surface a same-root-cause sibling that the
            dense/lexical legs miss. Bypasses ``_MIN_SEARCH_RELEVANCE`` (siblings
            score ~0.05 on text) with a fixed floor, and never downgrades a
            problem already matched at a higher score by another leg."""
            pid = str(problem.problem_id)
            if pid in rows_by_id:
                return
            row = self._row_from_problem(problem, 0.0, full, search_text=search_text)
            row["similarity_score"] = _PATTERN_MATCH_SCORE
            row["match_quality"] = "pattern"
            row["match_reasons"] = [f"root-cause class match: {pattern_class}"]
            rows_by_id[pid] = row

        # raw_score=0.0 so the vector / RRF leg decides ranking; quality
        # tier still derives from token analysis in _classify_match_quality.
        signature_candidates = self._exact_error_signature_candidates(search_text)
        for problem in signature_candidates:
            add_candidate(problem, 0.0)
        signature_used = bool(signature_candidates)

        diagnostics = SearchDiagnostics(
            backend="unavailable",
            pgvector_available=False,
            dense_hits=0,
            sparse_hits=0,
        )
        keyword_fallback_used = False
        semantic_fallback_dense_hits = 0

        if query_embedding is not None or normalized_query:
            hybrid, diagnostics = self._problems.find_hybrid_with_diagnostics(
                query_embedding=query_embedding,
                query_text=normalized_query,
                limit=max(limit * 2, 20),
            )
            for problem, score in hybrid:
                add_candidate(problem, score)

        if not rows_by_id and query_embedding is not None:
            for problem, score in self._problems.find_similar_scored(query_embedding):
                add_candidate(problem, score)
                semantic_fallback_dense_hits += 1

        if semantic_fallback_dense_hits:
            diagnostics = dataclass_replace(
                diagnostics,
                dense_hits=diagnostics.dense_hits + semantic_fallback_dense_hits,
            )

        if not rows_by_id:
            query_terms = self._extract_terms(normalized_query)
            for problem in self._problems.list_all():
                if problem.review_status != "approved":
                    continue
                if normalized_query and query_terms:
                    desc_lower = problem.description.lower()
                    if not any(term in desc_lower for term in query_terms):
                        continue
                add_candidate(problem, 0.2)
                keyword_fallback_used = True

        # Cross-task root-cause leg (additive): the caller classifies the bug
        # into a root-cause class and passes ``pattern_class``; problems carrying
        # the matching ``pattern:<slug>`` tag are surfaced even when their surface
        # text is unrelated. Runs after the dense/lexical legs so a genuine
        # same-task hit keeps its higher score and rank.
        if pattern_class:
            wanted_tag = f"{_PATTERN_TAG_PREFIX}{pattern_class}"
            for problem in self._problems.list_all():
                if problem.review_status != "approved":
                    continue
                if wanted_tag in (problem.tags or []):
                    add_pattern_candidate(problem)

        rows = list(rows_by_id.values())
        # Honest match labeling BEFORE ranking: a row with no best_solution
        # offers no actionable help. Stamp ``has_help`` and demote its
        # ``match_quality`` to the no-solution tier *before* the sort/truncation
        # below, so a hollow signature/keyword hit sinks instead of seizing a top
        # slot and crowding out a genuine solution-bearing hit at a small limit
        # (which would also make the recurrence instrument read rows[0] as a
        # miss). Confidence-provenance enrichment still runs post-truncation.
        for row in rows:
            has_help = row.get("best_solution") is not None
            row["has_help"] = has_help
            if not has_help:
                row["match_quality"] = _NO_SOLUTION_TIER
        # Phase 2 reranking: apply the cross-encoder to the top
        # ``rerank_top_k`` candidates by ``similarity_score`` before final
        # truncation to ``limit``. The reranker reorders candidates within
        # the same ``match_quality`` tier; the two-key sort below preserves
        # tier ordering so a "poor" lexical hit cannot leapfrog a true
        # ``"exact"`` substring match no matter what the reranker says.
        rows = self._apply_reranker(search_text, rows)
        _quality_rank = {
            "exact": 0,
            "strong": 1,
            "partial": 2,
            "pattern": 3,
            "poor": 4,
        }
        rows.sort(
            key=lambda item: (
                _quality_rank.get(item["match_quality"], 4),
                -item.get("rerank_score", 0.0),
                -item["similarity_score"],
            )
        )
        rows = rows[: max(limit, 0)]

        # Provenance enrichment runs *after* truncation so per-row
        # outcome lookups scale with response size, not the unfiltered
        # candidate pool (~50× before truncation).
        self._attach_search_provenance(rows)

        if include:
            for row in rows:
                self._enrich_search_row(row, include)

        search_mode = self._classify_search_mode(
            diagnostics=diagnostics,
            keyword_fallback_used=keyword_fallback_used,
            signature_used=signature_used,
            rows=rows,
        )
        return rows, search_mode

    @staticmethod
    def _classify_search_mode(
        *,
        diagnostics: SearchDiagnostics,
        keyword_fallback_used: bool,
        signature_used: bool,
        rows: list[dict],
    ) -> SearchMode:
        """Map low-level retrieval signals into the user-facing label.

        Precedence (matches the docstring on _search_problems):
        no_match → in_memory_scan → keyword_fallback → hybrid →
        vector_only → lexical_only → signature_match. ``in_memory_scan``
        wins over leg-flavoured labels because it's an architectural
        fact the operator needs to see; the dense/sparse split inside
        it is secondary.
        """
        if not rows:
            return "no_match"
        if diagnostics.backend == "memory":
            return "in_memory_scan"
        if keyword_fallback_used:
            return "keyword_fallback"
        if diagnostics.dense_hits > 0 and diagnostics.sparse_hits > 0:
            return "hybrid"
        if diagnostics.dense_hits > 0:
            return "vector_only"
        if diagnostics.sparse_hits > 0:
            return "lexical_only"
        if signature_used:
            return "signature_match"
        return "no_match"

    def _row_from_problem(
        self,
        problem: Problem,
        score: float,
        full: bool,
        search_text: str | None = None,
    ) -> dict:
        relevance_score, quality, reasons = self._score_problem_relevance(
            problem, search_text or "", score
        )
        return {
            "problem_id": str(problem.problem_id),
            "description": problem.description,
            "tags": problem.tags or [],
            "best_confidence": problem.best_confidence,
            "solution_count": problem.solution_count,
            "similarity_score": relevance_score,
            "match_quality": quality,
            "match_reasons": reasons,
            "best_solution": self._pick_best_solution(problem.problem_id, full=full),
            "created_at": problem.created_at.isoformat(),
        }

    def _exact_error_signature_candidates(self, search_text: str) -> list[Problem]:
        """Pre-filter approved problems whose ``error_signature`` plausibly
        addresses the query. Two admission paths:

        * Substring match between normalized query and signature (either
          direction) — the "exact" tier.
        * Token-overlap with at least ``_DISTINCTIVE_OVERLAP_MIN`` distinctive
          tokens AND Jaccard >= ``_SIGNATURE_JACCARD_MIN`` — the "strong"
          tier when keyed on signature.

        The previous single-distinctive-token rule produced 27% high-confidence
        false positives in the 22-Agent simulation (Docker socket query
        matched a Docker rootless tmp problem; TS2742 query matched an Xcode
        pbxproj problem). The double gate eliminates them without losing any
        legitimate match in the eval set.
        """
        normalized_query = _normalize_search_text(search_text)
        if not normalized_query:
            return []
        query_tokens = set(_tokenize_search_text(search_text))
        distinctive_query = {
            t for t in query_tokens if len(t) >= _DISTINCTIVE_TOKEN_MIN_LENGTH
        }

        matches: list[Problem] = []
        for problem in self._problems.list_all():
            if problem.review_status != "approved" or not problem.error_signature:
                continue
            signature = _normalize_search_text(problem.error_signature)
            signature_tokens = set(_tokenize_search_text(problem.error_signature))
            if _signature_match(normalized_query, signature):
                matches.append(problem)
                continue
            matching_distinctive = distinctive_query & signature_tokens
            if (
                len(matching_distinctive) >= _DISTINCTIVE_OVERLAP_MIN
                and _jaccard(query_tokens, signature_tokens) >= _SIGNATURE_JACCARD_MIN
            ):
                matches.append(problem)
        return matches

    def _classify_match_quality(
        self, problem: Problem, search_text: str, raw_score: float
    ) -> tuple[str, list[str], dict[str, float]]:
        """Classify ``problem`` into a quality tier for ``search_text``.

        Returns ``(quality, reasons, signals)`` where ``signals`` carries the
        pre-computed overlap / Jaccard values so ``_compute_relevance_score``
        does not re-tokenize.

        Tiers, in priority order:

        * ``"exact"`` — full normalized query is a substring of the
          ``error_signature`` (or vice versa). The only path that earns
          ``similarity_score == 1.0``.
        * ``"strong"`` — distinctive overlap with ``error_signature`` clears
          both gates (>= 3 distinct tokens AND Jaccard >= 0.35), OR the raw
          vector score >= 0.6 (real embedding providers only — under the
          ``fallback`` provider the vector score caps out at ``"partial"``),
          OR lexical overlap_ratio >= 0.5.
        * ``"partial"`` — overlap_ratio or raw_score in [0.25, threshold).
        * ``"poor"`` — fallback, kept only when no better candidate exists.
        """
        normalized_query = _normalize_search_text(search_text)
        query_tokens = set(_tokenize_search_text(search_text))
        candidate_text = " ".join(
            part
            for part in (
                problem.description,
                problem.error_signature or "",
                " ".join(problem.tags or []),
            )
            if part
        )
        candidate_tokens = set(_tokenize_search_text(candidate_text))
        signature_tokens: set[str] = set()
        if problem.error_signature:
            signature_tokens = set(_tokenize_search_text(problem.error_signature))

        overlap_ratio = len(query_tokens & candidate_tokens) / max(len(query_tokens), 1)
        signature_jaccard = (
            _jaccard(query_tokens, signature_tokens) if signature_tokens else 0.0
        )
        signals = {
            "overlap_ratio": overlap_ratio,
            "signature_jaccard": signature_jaccard,
        }
        reasons: list[str] = []
        # The deterministic fallback embedder false-matches unrelated
        # error-ish texts (any two sit at ~0.6+ cosine), so when it is the
        # active provider the raw vector score may not mint a tier above
        # "partial". Lexical signals keep full authority — they never depend
        # on embedding quality.
        semantic_trusted = self._embedding_provider_name != "fallback"

        if problem.error_signature:
            signature = _normalize_search_text(problem.error_signature)
            if _signature_match(normalized_query, signature):
                return "exact", ["error_signature"], signals

            distinctive_query = {
                t for t in query_tokens if len(t) >= _DISTINCTIVE_TOKEN_MIN_LENGTH
            }
            matching_distinctive = distinctive_query & signature_tokens
            if (
                len(matching_distinctive) >= _DISTINCTIVE_OVERLAP_MIN
                and signature_jaccard >= _SIGNATURE_JACCARD_MIN
            ):
                reasons.append("error_signature")
                if semantic_trusted and raw_score >= 0.6:
                    reasons.append("semantic")
                return "strong", reasons, signals

        if query_tokens & candidate_tokens:
            reasons.append("lexical_overlap")

        if semantic_trusted and raw_score >= 0.6:
            reasons.append("semantic")
            return "strong", reasons, signals

        if overlap_ratio >= 0.5:
            return "strong", reasons, signals

        if overlap_ratio >= _MIN_SEARCH_RELEVANCE:
            return "partial", reasons, signals

        if raw_score >= _MIN_SEARCH_RELEVANCE:
            if "semantic" not in reasons:
                reasons.append("semantic")
            return "partial", reasons, signals

        return "poor", reasons, signals

    def _compute_relevance_score(
        self,
        *,
        quality: str,
        raw_score: float,
        overlap_ratio: float,
        signature_jaccard: float,
    ) -> float:
        """Numeric similarity score derived from the classification signals.

        ``1.0`` is reserved for ``quality == "exact"``. Every other tier is
        capped at ``_NON_EXACT_SCORE_CAP`` (0.95) so token-overlap false
        positives can never inflate a downstream Bayesian confidence to the
        same level as a confirmed substring match.
        """
        if quality == "exact":
            return 1.0
        score = max(raw_score, overlap_ratio, signature_jaccard)
        return min(score, _NON_EXACT_SCORE_CAP)

    def _score_problem_relevance(
        self, problem: Problem, search_text: str, raw_score: float
    ) -> tuple[float, str, list[str]]:
        """Compatibility shim that returns the tuple ``_row_from_problem``
        consumes. Composes ``_classify_match_quality`` + ``_compute_relevance_score``.
        """
        quality, reasons, signals = self._classify_match_quality(
            problem, search_text, raw_score
        )
        score = self._compute_relevance_score(
            quality=quality,
            raw_score=raw_score,
            overlap_ratio=signals["overlap_ratio"],
            signature_jaccard=signals["signature_jaccard"],
        )
        return score, quality, reasons

    def _enrich_search_row(self, row: dict, include: set[str]) -> None:
        problem_id = UUID(row["problem_id"])
        best = row.get("best_solution")
        best_solution_id = (
            UUID(best["solution_id"]) if best and best.get("solution_id") else None
        )

        if "solutions" in include:
            all_solutions = self._solutions.list_by_problem(problem_id)
            models = self._agent_models_map({s.author_id for s in all_solutions})
            row["solutions"] = [
                _solution_to_dict(s, models.get(s.author_id)) for s in all_solutions
            ]

        if "outcomes" in include:
            if best_solution_id is None:
                row["outcomes"] = []
            else:
                outs = self._outcomes.list_by_solution(best_solution_id)
                models = self._agent_models_map({o.reporter_id for o in outs})
                row["outcomes"] = [
                    _outcome_to_dict(o, models.get(o.reporter_id)) for o in outs
                ]

        if "lineage" in include:
            row["lineage"] = (
                self.get_solution_lineage(best_solution_id)
                if best_solution_id is not None
                else []
            )

    def _ensure_agent_exists(self, agent_id: UUID) -> None:
        if self._agents.get(agent_id) is None:
            raise UnauthorizedError("Invalid API Key")

    def _llm_model_for_author(
        self, author_id: UUID, override: str | None = None
    ) -> str | None:
        if override is not None:
            return override
        agent = self._agents.get(author_id)
        return agent.model_type if agent else None

    def _agent_models_map(self, agent_ids: set[UUID]) -> dict[UUID, str | None]:
        return {aid: self._llm_model_for_author(aid, None) for aid in agent_ids}

    @staticmethod
    def _display_llm(
        models: dict[UUID, str | None],
        agent_id: UUID,
        stored: str | None,
    ) -> str | None:
        if stored:
            return stored
        return models.get(agent_id)

    def _apply_reranker(self, search_text: str, rows: list[dict]) -> list[dict]:
        """Stamp ``rerank_score`` onto rows; reorder within quality tier only.

        Strategy:

        1. Take the top ``settings.rerank_top_k`` rows by current
           ``similarity_score`` — this caps reranker spend per query and
           matches the recommended pool size for ``rerank-2.5-lite`` (~80-120ms
           p50 at top-30).
        2. Hand the document strings to the reranker callable. Document text
           is ``description + " " + (error_signature or "")`` — same shape
           the cross-encoder was trained on.
        3. Map the returned indices to dense scores by their rank position
           (1.0 for the best, ``1 - rank/N`` after that). The actual
           magnitudes don't matter — only the ordering does, since the final
           sort uses ``rerank_score`` strictly as a tie-breaker within
           ``match_quality`` tier.
        4. Tail rows (beyond ``rerank_top_k``) get ``rerank_score = 0.0`` so
           the sort key remains well-defined for every row.

        When the reranker is the NoOp identity (no Voyage key, exhausted
        rate-limit bucket, or upstream failure), every reranked row simply
        keeps its original relative order — equivalent to Phase 1 behaviour.
        """
        if not rows or not settings.rerank_enabled:
            for row in rows:
                row.setdefault("rerank_score", 0.0)
            return rows

        # Sort once by similarity_score so the slice is the highest-quality
        # pool the reranker will see; the final two-key sort runs after this.
        rows.sort(key=lambda item: item["similarity_score"], reverse=True)
        top_k = max(settings.rerank_top_k, 0)
        head = rows[:top_k]
        tail = rows[top_k:]

        documents: list[str] = []
        for row in head:
            sig = self._row_signature(row)
            doc = f"{row['description']} {sig}".strip() if sig else row["description"]
            documents.append(doc)

        try:
            order = self._rerank_fn(search_text, documents, len(head))
        except Exception as e:  # noqa: BLE001 - degrade gracefully on any error
            logger.warning("rerank-failed-identity-fallback error=%s", e)
            for row in head:
                row["rerank_score"] = 0.0
            for row in tail:
                row["rerank_score"] = 0.0
            return rows

        # ``order`` may be shorter than ``head`` (e.g., reranker truncated).
        n = len(head)
        for rank, idx in enumerate(order):
            if 0 <= idx < n:
                head[idx]["rerank_score"] = 1.0 - (rank / max(n, 1))
        # Any head row not visited by ``order`` keeps a defined score.
        for row in head:
            row.setdefault("rerank_score", 0.0)
        for row in tail:
            row["rerank_score"] = 0.0
        return head + tail

    def _row_signature(self, row: dict) -> str:
        """Best-effort retrieval of an error signature attached to a row.

        Search rows are constructed by ``_row_from_problem`` which doesn't
        copy ``error_signature`` into the dict. We re-fetch by problem_id so
        the reranker sees the same text the user would.
        """
        try:
            problem = self._problems.get(UUID(row["problem_id"]))
        except Exception:  # noqa: BLE001
            return ""
        if problem is None:
            return ""
        return problem.error_signature or ""

    def _safe_embed(
        self, text: str, *, input_type: str = "query"
    ) -> list[float] | None:
        """Embed ``text`` with the configured provider; ``None`` on any failure.

        ``input_type`` selects the asymmetric pole for Voyage v3-large
        (``"query"`` for live search, ``"document"`` for persisted
        embeddings). Symmetric providers ignore it. Failures are swallowed
        and downgrade the search/dedup path to a keyword fallback rather
        than raising — agentbook's read tier must stay available even when
        the embedding provider is degraded.
        """
        if self._embedding_provider is None or not text:
            return None

        try:
            return self._embedding_provider.embed(text, input_type=input_type)
        except Exception as e:
            logger.warning(f"Embedding failed, using fallback: {e}")
            return None

    def _compose_search_text(self, query: str, error_log: str | None) -> str:
        parts = [query.strip()]
        if error_log:
            parts.append(error_log.strip())
        return "\n".join(part for part in parts if part)

    def _extract_terms(self, text: str) -> list[str]:
        terms = [term.strip() for term in text.replace("\n", " ").split(" ")]
        return [term for term in terms if term]

    def _extract_model_from_agent_info(self, raw_agent_info: str | None) -> str | None:
        if raw_agent_info is None:
            return None

        try:
            payload = json.loads(raw_agent_info)
        except json.JSONDecodeError:
            return None

        model = payload.get("model")
        if not isinstance(model, str):
            return None

        if "-" not in model:
            return model
        return model.split("-", maxsplit=1)[0]

    # --- Unified review lifecycle methods ---

    def update_review(
        self,
        content_id: UUID,
        status: str,
        score: float,
        reviewed_at: datetime,
    ) -> Problem | Solution:
        p = self._problems.get(content_id)
        if p is not None:
            p.review_status = status
            p.review_score = score
            p.reviewed_at = reviewed_at
            self._problems.update(p)
            return p
        s = self._solutions.get(content_id)
        if s is not None:
            s.review_status = status
            s.review_score = score
            s.reviewed_at = reviewed_at
            self._solutions.update(s)
            return s
        raise NotFoundError(f"Content {content_id} not found")

    def delete_content(self, content_id: UUID) -> None:
        p = self._problems.get(content_id)
        if p is not None:
            for sol in self._solutions.list_by_problem(p.problem_id):
                self._solutions.delete(sol.solution_id)
            self._problems.delete(content_id)
            return
        s = self._solutions.get(content_id)
        if s is not None:
            was_visible = _is_visible_solution(s)
            self._solutions.delete(content_id)
            prob = self._problems.get(s.problem_id)
            # solution_count counts only visible solutions — decrement when
            # the purged row was one (candidates/demoted were never tallied).
            if prob is not None and was_visible:
                prob.solution_count = max(0, prob.solution_count - 1)
                self._problems.update(prob)
            return
        raise NotFoundError(f"Content {content_id} not found")

    def get_unreviewed_problems(
        self,
        limit: int = 100,
        retry_error_before: datetime | None = None,
    ) -> list[Problem]:
        return self._problems.find_unreviewed(
            limit=limit, retry_error_before=retry_error_before
        )

    def get_unreviewed_solutions(
        self,
        limit: int = 100,
        retry_error_before: datetime | None = None,
    ) -> list[Solution]:
        return self._solutions.find_unreviewed(
            limit=limit, retry_error_before=retry_error_before
        )

    def list_problems(
        self,
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "created_at",
        order: str = "desc",
        viewer_id: UUID | None = None,
        include_pending: bool = False,
    ) -> list[dict]:
        all_problems = self._problems.list_all()
        _sort_key = {
            "created_at": lambda p: p.created_at,
            "best_confidence": lambda p: p.best_confidence,
            "solution_count": lambda p: p.solution_count,
            "last_activity_at": lambda p: p.last_activity_at,
        }.get(sort_by, lambda p: p.created_at)
        all_problems.sort(key=_sort_key, reverse=(order != "asc"))

        result = []
        author_models: dict[UUID, str | None] = {}

        def _author_llm(author_id: UUID) -> str | None:
            if author_id not in author_models:
                author_models.update(self._agent_models_map({author_id}))
            return self._display_llm(author_models, author_id, None)

        for p in all_problems:
            if p.review_status == "approved":
                result.append(
                    {
                        "problem_id": str(p.problem_id),
                        "author_id": str(p.author_id),
                        "llm_model": _author_llm(p.author_id),
                        "description": p.description,
                        "best_confidence": p.best_confidence,
                        "solution_count": p.solution_count,
                        "review_status": p.review_status,
                        "has_canonical": p.canonical_solution_id is not None,
                        "tags": p.tags or [],
                        "error_signature": p.error_signature,
                        "environment": p.environment,
                        "created_at": p.created_at.isoformat(),
                        "last_activity_at": p.last_activity_at.isoformat(),
                        "is_being_researched": _is_being_researched(p),
                    }
                )
            elif include_pending and viewer_id is not None and p.author_id == viewer_id:
                result.append(
                    {
                        "problem_id": str(p.problem_id),
                        "author_id": str(p.author_id),
                        "llm_model": _author_llm(p.author_id),
                        "description": p.description,
                        "best_confidence": p.best_confidence,
                        "solution_count": p.solution_count,
                        "review_status": p.review_status or "pending",
                        "has_canonical": p.canonical_solution_id is not None,
                        "tags": p.tags or [],
                        "error_signature": p.error_signature,
                        "environment": p.environment,
                        "created_at": p.created_at.isoformat(),
                        "last_activity_at": p.last_activity_at.isoformat(),
                    }
                )
        return result[offset : offset + limit]

    def get_agentbook(self, problem_id: UUID) -> dict:
        problem = self._problems.get(problem_id)
        if problem is None or problem.review_status == "removed":
            raise NotFoundError(f"Problem {problem_id} not found")

        all_solutions = self._solutions.list_by_problem(problem_id)
        # Exclude unconfirmed candidates and rejected (demoted) proposals from
        # the public view; show only validated (base/promoted) solutions.
        visible_solutions = [s for s in all_solutions if _is_visible_solution(s)]
        seed_ids = self._seed_agent_ids()

        agent_ids: set[UUID] = {problem.author_id}
        for s in visible_solutions:
            agent_ids.add(s.author_id)
        canonical_sol = None
        if problem.canonical_solution_id:
            canonical_sol = self._solutions.get(problem.canonical_solution_id)
            if canonical_sol:
                agent_ids.add(canonical_sol.author_id)
        models = self._agent_models_map(agent_ids)

        canonical = None
        if canonical_sol:
            canonical = {
                "solution_id": str(canonical_sol.solution_id),
                "content": canonical_sol.content,
                "steps": canonical_sol.steps,
                "root_cause_pattern": canonical_sol.root_cause_pattern,
                "localization_cues": canonical_sol.localization_cues,
                "verification": canonical_sol.verification,
                "root_cause_class": canonical_sol.root_cause_class,
                "confidence": canonical_sol.confidence,
                "outcome_count": canonical_sol.outcome_count,
                "success_count": canonical_sol.success_count,
                "failure_count": canonical_sol.failure_count,
                "confidence_provenance": self._confidence_provenance(
                    canonical_sol, all_solutions
                ),
                **self._book_provenance(canonical_sol, seed_ids),
                "author_id": str(canonical_sol.author_id),
                "llm_model": self._display_llm(
                    models, canonical_sol.author_id, canonical_sol.llm_model
                ),
                "parent_solution_id": str(canonical_sol.parent_solution_id)
                if canonical_sol.parent_solution_id
                else None,
                "promotion_status": canonical_sol.promotion_status,
                "created_at": canonical_sol.created_at.isoformat(),
            }

        history = [
            {
                "solution_id": str(s.solution_id),
                "content": s.content,
                "steps": s.steps,
                "root_cause_pattern": s.root_cause_pattern,
                "localization_cues": s.localization_cues,
                "verification": s.verification,
                "root_cause_class": s.root_cause_class,
                "confidence": s.confidence,
                "outcome_count": s.outcome_count,
                "success_count": s.success_count,
                "failure_count": s.failure_count,
                "confidence_provenance": self._confidence_provenance(s, all_solutions),
                **self._book_provenance(s, seed_ids),
                "author_id": str(s.author_id),
                "llm_model": self._display_llm(models, s.author_id, s.llm_model),
                "parent_solution_id": str(s.parent_solution_id)
                if s.parent_solution_id
                else None,
                "promotion_status": s.promotion_status,
                "created_at": s.created_at.isoformat(),
                "review_status": s.review_status,
            }
            for s in visible_solutions
            if problem.canonical_solution_id is None
            or s.solution_id != problem.canonical_solution_id
        ]

        # Outcome summary across ALL visible solutions of the problem — a
        # reading agent judges how battle-tested the whole agentbook is, so a
        # non-top solution's failure must not be invisible in the headline
        # metric. Canonical source solutions are visible-equivalent for the
        # count even when hidden from the history list.
        summary_solution_ids = [s.solution_id for s in visible_solutions]
        if canonical_sol:
            summary_solution_ids.append(canonical_sol.solution_id)
            summary_solution_ids.extend(
                s.solution_id
                for s in all_solutions
                if s.canonical_id == canonical_sol.solution_id
            )
        summary_solution_ids = list(dict.fromkeys(summary_solution_ids))

        outcome_summary = {
            "total": 0,
            "successes": 0,
            "failures": 0,
            "recent_failure_notes": [],
        }
        if summary_solution_ids:
            problem_outcomes = self._outcomes.list_by_problem(
                problem_id, summary_solution_ids
            )
            if problem_outcomes:
                successes = sum(1 for o in problem_outcomes if o.success)
                failure_notes = [
                    o.notes for o in problem_outcomes if not o.success and o.notes
                ][-3:]
                outcome_summary = {
                    "total": len(problem_outcomes),
                    "successes": successes,
                    "failures": len(problem_outcomes) - successes,
                    "recent_failure_notes": failure_notes,
                }

        # Research summary (stall detection for autoresearch)
        if self._research_cycles is not None:
            cycles = self._research_cycles.list_by_problem(problem_id)
            last_at = self._research_cycles.get_last_researched_at(problem_id)
            stall_count = self._research_cycles.count_consecutive_no_improvement(
                problem_id
            )
            research_summary: dict = {
                "total_cycles": len(cycles),
                "last_status": cycles[0].status if cycles else None,
                "consecutive_no_improvement": stall_count,
                "last_researched_at": last_at.isoformat() if last_at else None,
            }
        else:
            research_summary = {
                "total_cycles": 0,
                "last_status": None,
                "consecutive_no_improvement": 0,
                "last_researched_at": None,
            }

        return {
            "problem_id": str(problem.problem_id),
            "description": problem.description,
            "tags": problem.tags or [],
            "error_signature": problem.error_signature,
            "environment": problem.environment,
            "created_at": problem.created_at.isoformat(),
            "author_llm_model": self._display_llm(models, problem.author_id, None),
            "canonical_solution": canonical,
            "reliance_target": self._resolve_reliance_target(problem_id),
            "solution_history": history,
            "best_confidence": problem.best_confidence,
            # Count only the validated solutions actually presented here
            # (canonical + solution_history). The stored ``problem
            # .solution_count`` also tallies demoted improve-candidates,
            # which this view deliberately hides — surfacing the raw count
            # made the trace response self-contradictory.
            "solution_count": len(visible_solutions),
            "has_canonical": problem.canonical_solution_id is not None,
            "outcome_summary": outcome_summary,
            "research_summary": research_summary,
            "is_being_researched": _is_being_researched(problem),
        }

    def _book_provenance(self, solution: Solution, seed_ids: frozenset[UUID]) -> dict:
        """Seeded-vs-organic badge for a book-view solution row.

        Same classification as the search surface's ``confidence_inputs`` so the
        public problem-detail page can flag a score no organic reporter has
        corroborated, not just the recall API.
        """
        prov = _provenance_from_outcomes(
            solution, self._outcomes.list_by_solution(solution.solution_id), seed_ids
        )
        return {
            "provenance": prov["provenance"],
            "seeded_reporters": prov["seeded_reporters"],
        }

    def _confidence_provenance(
        self, solution: Solution, all_solutions: list[Solution]
    ) -> dict:
        direct_outcomes = self._outcomes.list_by_solution(solution.solution_id)
        source_solutions = [
            s for s in all_solutions if s.canonical_id == solution.solution_id
        ]

        if source_solutions:
            inherited_outcomes = sum(s.outcome_count for s in source_solutions)
            successes = sum(s.success_count for s in source_solutions)
            failures = sum(s.failure_count for s in source_solutions)
            source = "synthesized_sources"
        else:
            inherited_outcomes = 0
            successes = solution.success_count
            failures = solution.failure_count
            source = "direct_outcomes" if direct_outcomes else "prior"

        return {
            "source": source,
            "direct_outcomes": len(direct_outcomes),
            "inherited_outcomes": inherited_outcomes,
            "successes": successes,
            "failures": failures,
            "source_solution_ids": [str(s.solution_id) for s in source_solutions],
        }

    def _pick_best_solution(self, problem_id: UUID, full: bool = False) -> dict | None:
        """Best-solution row excluding ``confidence_provenance``.

        Provenance is filled in by ``_attach_search_provenance`` after
        the candidate list is truncated to ``limit`` so the per-row
        ``list_by_solution`` cost scales with the response size, not
        the unfiltered candidate pool.
        """
        solutions = self._solutions.list_by_problem(problem_id)
        # Use the canonical visibility filter (approved AND not a pending
        # candidate / demoted proposal) so the search reliance target matches
        # get_agentbook(), trace, and solution_count. Filtering only on
        # review_status would let a higher-confidence but unpromoted candidate
        # surface here as the relied-upon solution while every other surface
        # hides it — a cross-surface reliance-target inconsistency.
        visible = [s for s in solutions if _is_visible_solution(s)]
        if not visible:
            return None
        best = max(visible, key=lambda s: s.confidence)
        if full:
            content_preview, content_truncated = best.content, False
        else:
            content_preview, content_truncated = _clean_preview(
                best.content, _SEARCH_PREVIEW_BUDGET
            )
        return {
            "solution_id": str(best.solution_id),
            "_solution_obj": best,  # popped during enrichment
            "confidence": best.confidence,
            "content": best.content,
            "content_preview": content_preview,
            "content_truncated": content_truncated,
            "steps": list(best.steps or []),
            "root_cause_pattern": best.root_cause_pattern,
            "localization_cues": list(best.localization_cues or []),
            "verification": list(best.verification or []),
            "root_cause_class": best.root_cause_class,
            "outcome_count": best.outcome_count,
        }

    def _attach_search_provenance(self, rows: list[dict]) -> None:
        """Fill in ``best_solution.confidence_inputs`` per surfaced row.

        Distinct field name from the lineage-shaped ``confidence_provenance``
        on the ``get_agentbook`` view: the search payload exposes the
        raw outcome counts that fed the Bayesian estimate, the agentbook
        view exposes which sibling solutions contributed via inheritance.
        """
        for row in rows:
            best = row.get("best_solution")
            if not best:
                continue
            solution = best.pop("_solution_obj", None)
            if solution is None:
                continue
            outcomes = self._outcomes.list_by_solution(solution.solution_id)
            best["confidence_inputs"] = _provenance_from_outcomes(
                solution, outcomes, self._seed_agent_ids()
            )

    # --- Problem/Solution/Outcome methods ---

    def resolve(
        self,
        agent_id: UUID,
        description: str,
        error_signature: str | None = None,
        environment: dict | None = None,
        auto_post: bool = True,
    ) -> dict:
        gate = check_spam(description, "problem")
        if not gate.passed:
            raise ValueError(gate.reason)

        matched_problems: list[Problem] = []
        if error_signature:
            p = self._problems.find_by_error_signature(error_signature)
            if p is not None:
                matched_problems.append(p)

        if not matched_problems:
            embedding = self._safe_embed(description, input_type="query")
            if embedding is not None:
                similar = self._problems.find_similar(embedding, threshold=0.7)
                matched_problems.extend(similar)

        seen: set[UUID] = set()
        all_solutions: list[Solution] = []
        for p in matched_problems:
            for sol in self._solutions.list_by_problem(p.problem_id):
                if sol.solution_id not in seen:
                    seen.add(sol.solution_id)
                    all_solutions.append(sol)

        if all_solutions:

            def _rank(sol: Solution) -> float:
                rate = (
                    sol.success_count / sol.outcome_count
                    if sol.outcome_count > 0
                    else sol.confidence
                )
                return 0.6 * rate + 0.4 * sol.confidence

            all_solutions.sort(key=_rank, reverse=True)
            sol_author_ids = {s.author_id for s in all_solutions}
            sol_models = self._agent_models_map(sol_author_ids)
            return {
                "status": "resolved",
                "problem_id": matched_problems[0].problem_id,
                "solutions": [
                    _solution_to_dict(s, sol_models.get(s.author_id))
                    for s in all_solutions
                ],
            }

        if auto_post:
            # auto_post is resolve()'s only persistence path; error_signature
            # and environment ride straight onto the public Problem, so gate
            # them like create_problem() does (description is gated above).
            struct_label = detect_secret_in(error_signature, environment)
            if struct_label is not None:
                raise ValueError(secret_rejection(struct_label).detail)
            embedding = self._safe_embed(description, input_type="document")
            new_problem = Problem(
                author_id=agent_id,
                description=description,
                error_signature=error_signature,
                environment=environment,
                embedding=embedding,
            )
            self._problems.add(new_problem)
            return {
                "status": "registered",
                "problem_id": new_problem.problem_id,
                "solutions": [],
            }

        return {"status": "no_solutions", "problem_id": None, "solutions": []}

    def contribute(
        self,
        author_id: UUID,
        description: str,
        error_signature: str | None = None,
        environment: dict | None = None,
        tags: list[str] | None = None,
        solution_content: str | None = None,
        solution_steps: list[str] | None = None,
        solution_root_cause_pattern: str | None = None,
        solution_localization_cues: list[str] | None = None,
        solution_verification: list[dict] | None = None,
        problem_id: UUID | None = None,
    ) -> dict:
        # If a specific problem_id is given, add solution to that existing problem
        if problem_id is not None:
            existing_problem = self._problems.get(problem_id)
            if existing_problem is None:
                raise NotFoundError("Problem not found")
            solution_id: UUID | None = None
            if solution_content is not None:
                new_solution = self.create_solution(
                    problem_id=problem_id,
                    author_id=author_id,
                    content=solution_content,
                    steps=solution_steps,
                    root_cause_pattern=solution_root_cause_pattern,
                    localization_cues=solution_localization_cues,
                    verification=solution_verification,
                )
                solution_id = new_solution.solution_id
            return {
                "status": "solution_added"
                if solution_id is not None
                else "problem_created",
                "problem_id": str(existing_problem.problem_id),
                "solution_id": str(solution_id) if solution_id is not None else None,
            }

        # Exact duplicates — the only tier that earns similarity 1.0, a
        # confirmed error_signature substring match — are refused instead of
        # advised: a fork of a byte-identical signature can never be the
        # better agentbook, and synthesis needs the outcome flow on ONE
        # problem. Every lower tier keeps the admit-and-advise contract
        # (pre-pilot bias: admit rather than wrongly block). Keyword-only
        # legs, so the refusal works without any embedding key.
        exact_duplicates = self._exact_duplicate_rows(description, error_signature)
        if exact_duplicates:
            return {
                "status": "duplicate_problem",
                "problem_id": None,
                "solution_id": None,
                "existing_problems": exact_duplicates,
                "advice": (
                    "An identical problem already exists (exact "
                    "error_signature match: problem "
                    f"{exact_duplicates[0]['problem_id']}). Nothing was "
                    "stored. Improve its solution (provide solution_id) or "
                    "attach your solution to it (provide problem_id) instead "
                    "of creating a duplicate."
                ),
            }

        # Create new problem via create_problem (runs gate check internally
        # and attaches the description embedding).
        new_problem = self.create_problem(
            author_id=author_id,
            description=description,
            error_signature=error_signature,
            environment=environment,
            tags=tags,
        )

        existing_similar = self._dedup_advisory(new_problem, description)

        solution_id = None
        if solution_content is not None:
            new_solution = self.create_solution(
                problem_id=new_problem.problem_id,
                author_id=author_id,
                content=solution_content,
                steps=solution_steps,
                root_cause_pattern=solution_root_cause_pattern,
                localization_cues=solution_localization_cues,
                verification=solution_verification,
            )
            solution_id = new_solution.solution_id

        if existing_similar:
            status = "similar_exists"
        elif solution_id is not None:
            status = "knowledge_created"
        else:
            status = "problem_created"

        result = {
            "status": status,
            "problem_id": str(new_problem.problem_id),
            "solution_id": str(solution_id) if solution_id is not None else None,
            "existing_problems": existing_similar or None,
        }
        if existing_similar:
            # Steer the agent to improve-mode instead of forking a duplicate:
            # one evolving agentbook per problem is what feeds synthesis.
            result["advice"] = (
                "A matching problem already exists. Provide solution_id to "
                "improve its solution instead of creating a duplicate."
            )
        return result

    def _exact_duplicate_rows(
        self, description: str, error_signature: str | None
    ) -> list[dict]:
        """Pre-create exact-duplicate rows for the contribute refusal gate.

        Classifies prior problems found via the keyword signature legs with
        the same read-path tiering and keeps only the ``"exact"`` tier (a
        confirmed ``error_signature`` substring match). Runs before the new
        problem exists, so only embedding-independent legs apply — the
        semantic ``find_similar`` leg stays advisory-only in
        ``_dedup_advisory``.
        """
        if not error_signature:
            return []
        search_text = f"{description} {error_signature}"
        candidates: dict[UUID, Problem] = {}
        prior = self._problems.find_by_error_signature(error_signature)
        if prior is not None:
            candidates[prior.problem_id] = prior
        for p in self._exact_error_signature_candidates(search_text):
            candidates[p.problem_id] = p

        rows: list[dict] = []
        for problem in candidates.values():
            score, quality, _reasons = self._score_problem_relevance(
                problem, search_text, 0.0
            )
            if quality != "exact":
                continue
            rows.append(
                {
                    "problem_id": str(problem.problem_id),
                    "match_quality": quality,
                    "similarity_score": score,
                    "description_preview": problem.description[:200],
                }
            )
        return rows

    def _dedup_advisory(self, new_problem: Problem, description: str) -> list[dict]:
        """Write-time dedup advisory, independent of embedding availability.

        Folds three legs against the just-created ``new_problem``:

        * exact ``error_signature`` match via
          ``ProblemRepository.find_by_error_signature`` (keyword-only, always
          available),
        * keyword error-signature candidates (lexical token / Jaccard),
        * semantic ``find_similar`` neighbours when an embedding was attached.

        Each surviving candidate is classified with the same tiering the read
        path uses (``_score_problem_relevance``); only ``exact`` / ``strong``
        tiers are reported so a paraphrase or identical signature surfaces the
        prior problem while unrelated lexical noise does not. Sorted strongest
        first.
        """
        search_text = description
        if new_problem.error_signature:
            search_text = f"{description} {new_problem.error_signature}"

        candidates: dict[UUID, Problem] = {}
        if new_problem.error_signature:
            prior = self._problems.find_by_error_signature(new_problem.error_signature)
            if prior is not None and prior.problem_id != new_problem.problem_id:
                candidates[prior.problem_id] = prior
        for p in self._exact_error_signature_candidates(search_text):
            if p.problem_id != new_problem.problem_id:
                candidates[p.problem_id] = p
        if new_problem.embedding is not None:
            for p in self._problems.find_similar(new_problem.embedding, threshold=0.9):
                if p.problem_id != new_problem.problem_id:
                    candidates[p.problem_id] = p

        advisory: list[dict] = []
        for problem in candidates.values():
            score, quality, _reasons = self._score_problem_relevance(
                problem, search_text, 0.0
            )
            if quality not in _GOOD_MATCH_TIERS:
                continue
            advisory.append(
                {
                    "problem_id": str(problem.problem_id),
                    "match_quality": quality,
                    "similarity_score": score,
                    "description_preview": problem.description[:200],
                }
            )

        advisory.sort(
            key=lambda row: (row["match_quality"] != "exact", -row["similarity_score"])
        )
        return advisory

    def report_outcome(
        self,
        reporter_id: UUID,
        solution_id: UUID,
        success: bool,
        environment: dict | None = None,
        notes: str | None = None,
        time_saved_seconds: int | None = None,
    ) -> dict:
        solution = self._solutions.get(solution_id)
        if solution is None:
            raise NotFoundError(f"Solution {solution_id} not found")

        # A demoted solution is a rejected dead end: it never appears in
        # solution_history, its confidence is never shown, and it cannot be
        # re-promoted. Accepting a report here burns one unit of the
        # reporter's 10/hour budget on a score nobody will ever see — fail
        # loud before the rate-limit accounting, mirroring the
        # improve-on-demoted rejection above.
        if solution.promotion_status == "demoted":
            parent_ref = (
                f"its parent solution {solution.parent_solution_id}"
                if solution.parent_solution_id is not None
                else "one of the problem's visible solutions"
            )
            raise ValueError(
                "cannot report an outcome on a demoted solution: the "
                "promotion gate rejected it, its confidence is never shown, "
                f"and it cannot be re-promoted — report on {parent_ref} "
                "instead"
            )

        now = datetime.now(tz=UTC)
        since = now - timedelta(hours=_RATE_WINDOW_HOURS)
        if self._outcomes.count_by_reporter(reporter_id, since=since) >= _RATE_LIMIT:
            oldest = self._outcomes.oldest_created_at_by_reporter(
                reporter_id, since=since
            )
            window = timedelta(hours=_RATE_WINDOW_HOURS)
            retry_after = (
                max(1, int((oldest + window - now).total_seconds()))
                if oldest is not None
                else int(window.total_seconds())
            )
            raise RateLimitError(
                f"Rate limit exceeded: max {_RATE_LIMIT} outcomes per "
                f"{_RATE_WINDOW_HOURS} hour",
                retry_after_seconds=retry_after,
            )

        weight = 0.5 if (notes and "partial" in notes.lower()) else 1.0
        kind: OutcomeKind = (
            "verified" if reporter_id == SANDBOX_AGENT_ID else "observed"
        )

        outcome, inserted = self._outcomes.upsert(
            Outcome(
                solution_id=solution_id,
                reporter_id=reporter_id,
                success=success,
                kind=kind,
                environment=environment,
                notes=notes,
                time_saved_seconds=time_saved_seconds,
                weight=weight,
            )
        )

        all_outcomes = self._outcomes.list_by_solution(solution_id)
        previous_counters = (
            solution.outcome_count,
            solution.success_count,
            solution.failure_count,
        )
        previous_confidence = solution.confidence
        previous_promotion = solution.promotion_status
        # Derive counters from ground truth — a re-report that flips
        # success would otherwise drift the cached counts (the inserted
        # path increments, the update path silently kept stale totals).
        _recompute_outcome_counters(solution, all_outcomes)
        num_effective = _count_effective_reporters(
            all_outcomes, self._agents, solution.author_id
        )
        new_confidence = calculate_confidence(
            all_outcomes,
            solution.author_id,
            num_effective_reporters=num_effective,
        )
        solution.confidence = new_confidence

        # Candidate promotion/demotion: validate improvement against parent before superseding
        if (
            solution.promotion_status == "candidate"
            and solution.parent_solution_id is not None
        ):
            parent = self._solutions.get(solution.parent_solution_id)
            if parent is not None:
                # Use the anti-Sybil effective count excluding synthetic
                # server identities — the same diversity signal the
                # confidence math relies on, minus the EVALUATOR/SANDBOX
                # agents that would otherwise let the autonomous loop
                # supersede a parent with zero real corroboration (R2).
                genuine_reporters = _count_effective_reporters(
                    all_outcomes,
                    self._agents,
                    solution.author_id,
                    exclude=_SYNTHETIC_AGENT_IDS,
                )
                if genuine_reporters >= 1 and new_confidence >= parent.confidence:
                    # Confirmed improvement — promote and supersede parent
                    solution.promotion_status = "promoted"
                    parent.canonical_id = solution.solution_id
                    self._solutions.update(parent)
                elif (
                    solution.outcome_count >= _DEMOTION_MIN_OUTCOMES
                    and new_confidence < parent.confidence
                ):
                    # Insufficient improvement after real data — demote.
                    # Threshold is 5 (was 2 pre-2026-05): two coordinated
                    # bots reporting failure could permanently kill a
                    # legitimate candidate before real users could weigh
                    # in. 5 is still cheap for genuine fail-loud signal
                    # but raises the cost of a successful sybil attack to
                    # 5 reporter identities + spending one each.
                    solution.promotion_status = "demoted"
                    solution.canonical_id = solution.parent_solution_id

        # Skip the write when the row would be byte-identical — a
        # repeat report with the same success value re-derives the
        # same counters/confidence and the merge would be a full-row
        # no-op UPSERT.
        current_counters = (
            solution.outcome_count,
            solution.success_count,
            solution.failure_count,
        )
        if (
            solution.confidence != previous_confidence
            or solution.promotion_status != previous_promotion
            or current_counters != previous_counters
        ):
            self._solutions.update(solution)

        problem = self._problems.get(solution.problem_id)
        if problem is not None:
            problem_dirty = False
            if new_confidence > problem.best_confidence:
                problem.best_confidence = new_confidence
                problem_dirty = True
            # A candidate that just promoted becomes a visible solution —
            # bring solution_count in line with the agentbook view.
            if (
                previous_promotion == "candidate"
                and solution.promotion_status == "promoted"
            ):
                problem.solution_count += 1
                problem_dirty = True
            if problem_dirty:
                self._problems.update(problem)

        # An outcome shifts confidence and can promote/demote a candidate —
        # both change what search returns (best_solution.confidence, visibility).
        self._invalidate_search_cache()

        confidence_capped_by = (
            "cold_start_floor"
            if (
                num_effective < COLD_START_MIN_REPORTERS
                and new_confidence >= COLD_START_FLOOR
            )
            else None
        )
        return {
            "status": "reported",
            "outcome_id": str(outcome.outcome_id),
            # A re-report by the same reporter on the same solution REPLACES the
            # prior outcome (upsert) rather than appending — so a reporter sees
            # one row per solution and a 0.0 delta is never confused with a lost
            # write. ``replaced`` is True iff this report overwrote a prior one.
            "replaced": not inserted,
            "solution_confidence_updated": new_confidence,
            # `or 0.0` collapses negative zero: round() of a tiny negative
            # recency drift yields -0.0, which JSON serializes as "-0.0".
            "confidence_delta": round(new_confidence - previous_confidence, 6) or 0.0,
            "external_reporters": num_effective,
            "external_reporters_for_full_confidence": COLD_START_MIN_REPORTERS,
            "confidence_capped_by": confidence_capped_by,
            "confidence_note": _confidence_explainer(
                new_confidence=new_confidence,
                previous_confidence=previous_confidence,
                external_reporters=num_effective,
                capped=confidence_capped_by is not None,
                outcome_success=success,
            ),
        }

    def inspect_resource(
        self,
        resource_id: UUID,
        include: list[str] | None = None,
    ) -> dict:
        problem = self._problems.get(resource_id)
        if problem is not None and problem.review_status == "removed":
            raise NotFoundError(f"No problem or solution found with id {resource_id}")
        if problem is not None:
            effective = include if include is not None else ["solutions", "similar"]
            # Mirror the public visibility filter used by get_agentbook():
            # unreviewed and improve-candidate/demoted solutions stay out of
            # trace, so MCP trace and REST GET /v1/problems/{id} agree.
            visible_sols = [
                s
                for s in self._solutions.list_by_problem(problem.problem_id)
                if _is_visible_solution(s)
            ]
            sols = visible_sols if "solutions" in effective else []
            agent_ids: set[UUID] = {problem.author_id}
            for s in sols:
                agent_ids.add(s.author_id)
            pmap = self._agent_models_map(agent_ids)
            pdata = _problem_to_dict(problem)
            # Report the count of solutions trace actually exposes, not the
            # raw stored counter — otherwise data.solution_count can
            # contradict the solutions list and the REST detail endpoint.
            pdata["solution_count"] = len(visible_sols)
            pdata["llm_model"] = self._display_llm(pmap, problem.author_id, None)
            result: dict = {"type": "problem", "data": pdata}
            if "solutions" in effective:
                result["solutions"] = [
                    _solution_to_dict(s, pmap.get(s.author_id)) for s in sols
                ]
            if "similar" in effective:
                if (
                    settings.knowledge_graph_enabled
                    and self._problem_relationships is not None
                ):
                    rels = self._problem_relationships.find_related(
                        problem.problem_id, min_score=0.3, limit=10
                    )
                    sim_ids: set[UUID] = set()
                    sim_problems: list[tuple[Problem, str, float]] = []
                    for rel in rels:
                        p = self._problems.get(rel.target_problem_id)
                        if p is not None:
                            sim_ids.add(p.author_id)
                            sim_problems.append((p, rel.relationship_type, rel.score))
                    smap = self._agent_models_map(sim_ids)
                    result["similar"] = []
                    for p, rel_type, rel_score in sim_problems:
                        d = _problem_to_dict(p)
                        d["llm_model"] = self._display_llm(smap, p.author_id, None)
                        d["relationship_type"] = rel_type
                        d["relationship_score"] = rel_score
                        result["similar"].append(d)
                elif problem.embedding:
                    similar = self._problems.find_similar(
                        problem.embedding, threshold=0.6
                    )
                    sim_ids = set()
                    for p in similar:
                        if p.problem_id != problem.problem_id:
                            sim_ids.add(p.author_id)
                    smap = self._agent_models_map(sim_ids)
                    result["similar"] = []
                    for p in similar:
                        if p.problem_id == problem.problem_id:
                            continue
                        d = _problem_to_dict(p)
                        d["llm_model"] = self._display_llm(smap, p.author_id, None)
                        result["similar"].append(d)
                else:
                    # Neither the knowledge graph nor an embedding is
                    # available — return an explicit empty list so callers
                    # can tell "no similar problems" from "key omitted".
                    result["similar"] = []
            # Expose the documented canonical/history/outcome keys (and the
            # unified reliance target) the API detail endpoint surfaces, so
            # MCP trace and GET /v1/problems/{id} agree rather than diverging
            # into trace-only ``data``/``solutions`` keys.
            agentbook = self.get_agentbook(problem.problem_id)
            result["canonical_solution"] = agentbook["canonical_solution"]
            result["solution_history"] = agentbook["solution_history"]
            result["outcome_summary"] = agentbook["outcome_summary"]
            result["reliance_target"] = agentbook["reliance_target"]
            return result

        solution = self._solutions.get(resource_id)
        if solution is not None:
            effective = include if include is not None else ["outcomes"]
            outs = (
                self._outcomes.list_by_solution(solution.solution_id)
                if "outcomes" in effective
                else []
            )
            oids: set[UUID] = {solution.author_id}
            for o in outs:
                oids.add(o.reporter_id)
            omap = self._agent_models_map(oids)
            sdata = _solution_to_dict(solution, omap.get(solution.author_id))
            result = {"type": "solution", "data": sdata}
            if "outcomes" in effective:
                result["outcomes"] = [
                    _outcome_to_dict(o, omap.get(o.reporter_id)) for o in outs
                ]
            return result

        raise NotFoundError(f"No problem or solution found with id {resource_id}")

    def get_live_research_snapshot(self) -> dict:
        """Returns the live-research snapshot for the dashboard banner.

        Shape:
            {
                "active": [
                    {
                        "problem_id": str,
                        "description": str,           # truncated to 300 chars
                        "solution_count": int,
                        "best_confidence": float,
                        "research_started_at": str,   # ISO 8601 UTC
                        "elapsed_seconds": int,
                    },
                    ...                                # ordered by research_started_at DESC
                ],
                "last_cycle_at": str | None,           # ISO 8601 UTC or None
                "now": str,                            # ISO 8601 UTC
            }

        The active list is filtered through the existing 360s freshness window
        (RESEARCH_TIMEOUT_SECONDS). last_cycle_at is the global
        MAX(research_cycles.created_at). All timestamps are ISO 8601 strings.
        """
        now = utc_now()
        active_problems = self._problems.list_being_researched(
            timeout_seconds=RESEARCH_TIMEOUT_SECONDS
        )
        active = [
            {
                "problem_id": str(p.problem_id),
                "description": p.description[:300],
                "solution_count": p.solution_count,
                "best_confidence": p.best_confidence,
                "research_started_at": p.research_started_at.isoformat(),
                "elapsed_seconds": int((now - p.research_started_at).total_seconds()),
            }
            for p in active_problems
        ]
        last_cycle_at: datetime | None = None
        recent_cycles: list[dict] = []
        cycles_last_7_days = 0
        if self._research_cycles is not None:
            last_cycle_at = self._research_cycles.get_latest_cycle_at()
            since_7d = now - timedelta(days=7)
            cycles_last_7_days = self._research_cycles.count_since(since_7d)
            for cycle in self._research_cycles.list_recent(5):
                problem = self._problems.get(cycle.problem_id)
                description = (
                    problem.description[:72]
                    if problem is not None
                    else "Unknown memory"
                )
                recent_cycles.append(
                    {
                        "problem_id": str(cycle.problem_id),
                        "description": description,
                        "status": cycle.status,
                        "created_at": cycle.created_at.isoformat(),
                        "new_confidence": cycle.new_confidence,
                    }
                )
        return {
            "active": active,
            "last_cycle_at": last_cycle_at.isoformat() if last_cycle_at else None,
            "recent_cycles": recent_cycles,
            "cycles_last_7_days": cycles_last_7_days,
            "now": now.isoformat(),
        }

    def get_radar(self) -> dict:
        cutoff = datetime.now(tz=UTC) - timedelta(hours=24)
        all_problems = self._problems.list_all()

        # Two queries: solution_ids per problem + recent outcomes flat.
        # Per-problem recent_count is just a Counter lookup — the older
        # bucket-by-solution-id dict was redundant.
        problem_solution_ids = self._solutions.list_solution_ids_by_problem_ids(
            [p.problem_id for p in all_problems]
        )
        all_solution_ids = [
            sid for sids in problem_solution_ids.values() for sid in sids
        ]
        recent_count_by_sid: Counter[UUID] = Counter(
            o.solution_id
            for o in self._outcomes.list_by_solution_ids(all_solution_ids)
            if o.created_at >= cutoff
        )

        trending = []
        for p in all_problems:
            sol_ids = problem_solution_ids.get(p.problem_id, [])
            recent_count = sum(recent_count_by_sid.get(sid, 0) for sid in sol_ids)
            if recent_count > 0:
                rate = round(p.best_confidence, 2) if sol_ids else 0.0
                trending.append(
                    {
                        "problem_id": p.problem_id,
                        "description": p.description,
                        "agent_count": 1,
                        "solution_count": p.solution_count,
                        "resolution_rate": rate,
                        "last_24h_resolve_calls": recent_count,
                    }
                )
        trending.sort(key=lambda x: x["last_24h_resolve_calls"], reverse=True)

        new_unsolved = [
            {
                "problem_id": p.problem_id,
                "description": p.description,
                "agent_count": 1,
                "created_at": p.created_at,
            }
            for p in sorted(all_problems, key=lambda p: p.created_at, reverse=True)
            if p.solution_count == 0
        ][:10]

        degrading = [
            {
                "problem_id": p.problem_id,
                "description": p.description,
                "prev_confidence": round(min(p.best_confidence + 0.15, 1.0), 2),
                "curr_confidence": round(p.best_confidence, 2),
                "confidence_delta_7d": round(-0.15, 2),
            }
            for p in all_problems
            if p.solution_count > 0 and p.best_confidence < 0.5
        ][:10]

        return {
            "trending": trending,
            "new_unsolved": new_unsolved,
            "degrading": degrading,
        }

    def get_metrics(self) -> dict:
        all_problems = self._problems.list_all()
        total_problems = len(all_problems)

        solved = sum(1 for p in all_problems if p.solution_count > 0)
        resolution_rate = (
            round(solved / total_problems, 2) if total_problems > 0 else 0.0
        )

        # Bulk-load all solutions then all their outcomes in two queries —
        # replaces the previous N+M loop (one ``list_by_problem`` per
        # problem, one ``list_by_solution`` per solution).
        problem_solutions = self._solutions.list_by_problem_ids(
            [p.problem_id for p in all_problems]
        )
        all_solutions = [s for sols in problem_solutions.values() for s in sols]
        avg_confidence = (
            round(sum(s.confidence for s in all_solutions) / len(all_solutions), 2)
            if all_solutions
            else 0.0
        )

        all_outcomes = self._outcomes.list_by_solution_ids(
            [s.solution_id for s in all_solutions]
        )
        timed = [o.time_saved_seconds for o in all_outcomes if o.time_saved_seconds]
        median_ttr = int(sum(timed) / len(timed)) if timed else 0

        needs_synthesis = sum(
            1 for s in all_solutions if s.outcome_count >= 10 and s.confidence < 0.3
        )

        stale = sum(1 for s in all_solutions if s.outcome_count == 0)

        return {
            "resolution_rate": {
                "value": resolution_rate,
                "trend": None,
                "target": 0.80,
            },
            "median_ttr_seconds": {"value": median_ttr, "trend": None, "target": 300},
            "avg_solution_confidence": {
                "value": avg_confidence,
                "trend": None,
                "target": 0.75,
            },
            "knowledge_coverage": {"value": total_problems, "trend": None},
            "knowledge_freshness": {
                "value": round(resolution_rate * 0.9, 2),
                "trend": None,
                "target": 0.60,
            },
            "solutions_needing_synthesis": needs_synthesis,
            "stale_solutions": stale,
        }

    def get_usage_dashboard(self) -> dict:
        """Use-side flywheel-health snapshot.

        Aggregates outcome volume (total / last_7d / last_30d), the
        verified-vs-observed split, unique reporter counts per window,
        problems-with-outcomes vs total approved, and the top 10 problems
        ranked by total outcome count. All values derive from existing
        tables — no write hot path is added by this view.

        Ranking ties on ``outcome_count`` are broken by ``best_confidence``
        DESC and then ``problem_id`` ASC for determinism.

        ``outcomes.*`` vs ``problems.*`` asymmetry is intentional:
        ``outcomes`` counts every row in the ``outcomes`` table regardless
        of the parent problem's ``review_status`` (gives raw flow signal),
        while ``problems.*`` and ``top_problems_by_outcomes`` are scoped
        to ``review_status='approved'`` only (what end-users actually see).
        Pending/rejected problems can therefore drive ``outcomes.total``
        upward without appearing under ``problems.with_outcomes`` or in
        the top-10 list. ``test_usage_dashboard.py::test_…asymmetry`` is
        the regression guard for this contract.
        """
        now = utc_now()
        o = self._outcomes.aggregate_usage_metrics(now)

        approved = [
            p for p in self._problems.list_all() if p.review_status == "approved"
        ]
        approved_total = len(approved)

        # Bulk-load solution_ids per problem in ONE query (or one set scan
        # in-memory) — avoids N+1 round trips when the corpus has thousands
        # of approved problems. The previous per-problem ``list_by_problem``
        # loop turned this dashboard into a free DoS pedal on Postgres.
        problem_solutions = self._solutions.list_solution_ids_by_problem_ids(
            [p.problem_id for p in approved]
        )
        all_solution_ids: list[UUID] = [
            sid for sids in problem_solutions.values() for sid in sids
        ]

        counts_by_solution = self._outcomes.outcome_counts_by_solution_ids(
            all_solution_ids
        )

        problem_outcome_count: dict[UUID, int] = {
            pid: sum(counts_by_solution.get(sid, 0) for sid in sids)
            for pid, sids in problem_solutions.items()
        }

        approved_with_outcomes = sum(1 for c in problem_outcome_count.values() if c > 0)

        ranked_with_outcomes = sorted(
            (p for p in approved if problem_outcome_count.get(p.problem_id, 0) > 0),
            key=lambda p: (
                -problem_outcome_count[p.problem_id],
                -p.best_confidence,
                str(p.problem_id),
            ),
        )

        # Source classification keeps G3/G4 readable: without it, seeded
        # corpus activity and author self-reports read as demand.
        sources = self._outcomes.aggregate_outcome_sources(
            now,
            seed_reporter_ids=self._seed_agent_ids(),
            synthetic_reporter_ids=frozenset(_SYNTHETIC_AGENT_IDS),
        )
        organic_30d = sources["organic_external"]["last_30d"]
        total_30d = o["outcomes_last_30d"]

        return {
            "outcomes": {
                "total": o["outcomes_total"],
                "last_7_days": o["outcomes_last_7d"],
                "last_30_days": o["outcomes_last_30d"],
                "verified_total": o["verified_total"],
                "observed_total": o["observed_total"],
            },
            "outcome_sources": {
                **sources,
                "organic_share_30d": (organic_30d / total_30d) if total_30d else 0.0,
            },
            "reporters": {
                "unique_total": o["unique_reporters_total"],
                "unique_last_7_days": o["unique_reporters_7d"],
                "unique_last_30_days": o["unique_reporters_30d"],
            },
            "problems": {
                "total_approved": approved_total,
                "with_outcomes": approved_with_outcomes,
                "with_zero_outcomes": approved_total - approved_with_outcomes,
            },
            "top_problems_by_outcomes": [
                {
                    "problem_id": str(p.problem_id),
                    "description": _truncate_with_ellipsis(p.description),
                    "outcome_count": problem_outcome_count[p.problem_id],
                    "best_confidence": float(p.best_confidence),
                }
                for p in ranked_with_outcomes[:10]
            ],
        }

    def _seed_agent_ids(self) -> frozenset[UUID]:
        """Reserved seed/operator identities excluded from organic recurrence.

        Single source for the seed set; starts with the reserved sandbox agent
        so a seed-set replay can never inflate the organic-recurrence metric.
        Extended by the SEED_AGENT_IDS env (comma-separated UUIDs) so the
        operator can tag historical seed-corpus identities. A malformed token
        raises (fail loud) instead of silently classifying traffic as organic.
        """
        configured = frozenset(
            UUID(token.strip())
            for token in (settings.seed_agent_ids or "").split(",")
            if token.strip()
        )
        return frozenset({SANDBOX_AGENT_ID}) | configured

    def get_recurrence_density(self) -> dict:
        """Recurrence-density rollup over recorded real-traffic query events.

        Delegates the metric math to the query-event repo (which uses the
        shared ``compute_recurrence_rollup``); the service only seeds the
        exclusion set, filters per-problem rows to approved problems, and
        renames ``per_problem`` -> ``problems``. Returns the empty rollup when
        no query-event repo is wired (e.g. DEMO_MODE / legacy boot).
        """
        if self._query_events is None:
            return {
                "recurrence_density": 0.0,
                "organic_recurrence": 0.0,
                "total_independent_queries": 0,
                "problems": [],
            }
        rollup = self._query_events.recurrence_rollup(
            seed_agent_ids=self._seed_agent_ids(),
            since=utc_now() - timedelta(days=_RECURRENCE_WINDOW_DAYS),
        )
        per_problem = rollup.get("per_problem", [])
        # Bulk-fetch the (already <=100) per-problem ids in one round-trip, then
        # keep the approved ones — avoids both a full problems-table scan and a
        # per-row get (an N+1 on the DB path).
        candidate_ids = [
            pid for row in per_problem if (pid := row["problem_id"]) is not None
        ]
        approved_ids = {
            pid
            for pid, problem in self._problems.get_by_ids(candidate_ids).items()
            if problem.review_status == "approved"
        }
        problems = [
            {
                "problem_id": str(row["problem_id"]),
                "query_count": row["query_count"],
                "organic_recurrence": row["organic_recurrence"],
            }
            for row in per_problem
            if row["problem_id"] in approved_ids
        ]
        return {
            "recurrence_density": rollup["recurrence_density"],
            "organic_recurrence": rollup["organic_recurrence"],
            "total_independent_queries": rollup["total_independent_queries"],
            "problems": problems,
        }

    # --- Research loop methods ---

    def _validate_no_lineage_cycle(self, new_parent_id: UUID) -> None:
        """Validate that new_parent_id doesn't already have this solution in its ancestry.

        This prevents cycles that could occur from concurrent modifications or bugs.
        """
        visited: set[UUID] = set()
        current_id: UUID | None = new_parent_id

        while current_id is not None:
            if current_id in visited:
                raise ValueError("Cycle detected in parent lineage")
            visited.add(current_id)
            parent = self._solutions.get(current_id)
            current_id = parent.parent_solution_id if parent else None

    def _improve_solution_with_retry(
        self,
        author_id: UUID,
        solution_id: UUID,
        improved_content: str,
        improved_steps: list[str] | None,
        reasoning: str,
        llm_model: str | None = None,
        root_cause_pattern: str | None = None,
        localization_cues: list[str] | None = None,
        verification: list[dict] | None = None,
        max_retries: int = 3,
    ) -> dict:
        """Wrapper with retry logic for concurrent modification handling."""
        for attempt in range(max_retries):
            try:
                return self._improve_solution_impl(
                    author_id,
                    solution_id,
                    improved_content,
                    improved_steps,
                    reasoning,
                    llm_model,
                    root_cause_pattern=root_cause_pattern,
                    localization_cues=localization_cues,
                    verification=verification,
                )
            except ConcurrentModificationError as e:
                if attempt == max_retries - 1:
                    raise
                # Exponential backoff with jitter: prevents thundering herd
                base_delay = 0.1 * (2**attempt)
                jitter = random.uniform(0, 0.05)  # 0-50ms random jitter
                delay = base_delay + jitter
                logger.warning(
                    f"Concurrent modification detected, retrying in {delay:.3f}s: {e}"
                )
                time.sleep(delay)
                # Reload problem to get latest version
                continue
        raise RuntimeError("Unreachable")

    def improve_solution(
        self,
        solution_id: UUID,
        improved_content: str,
        improved_steps: list[str] | None = None,
        reasoning: str = "",
        author_id: UUID | None = None,
        llm_model: str | None = None,
        root_cause_pattern: str | None = None,
        localization_cues: list[str] | None = None,
        verification: list[dict] | None = None,
    ) -> dict:
        """Public API with retry logic."""
        _author_id = author_id or UUID("00000000-0000-0000-0000-000000000001")
        self._check_write_rate(_author_id)
        return self._improve_solution_with_retry(
            _author_id,
            solution_id,
            improved_content,
            improved_steps,
            reasoning,
            llm_model,
            root_cause_pattern=root_cause_pattern,
            localization_cues=localization_cues,
            verification=verification,
        )

    def verify_solution(self, solution_id: UUID, agent_id: UUID) -> dict:
        """Enqueue a sandbox-backed verification for a solution.

        Returns an envelope immediately. When a real SandboxProvider is
        configured the sandbox run is triggered inline (the provider is
        expected to be fast enough; task 013 does not add async queueing
        beyond what the underlying provider already supports). On success
        a verified Outcome is persisted via ``_run_sandbox_evaluation``.
        """
        solution = self._solutions.get(solution_id)
        if solution is None:
            raise NotFoundError(f"Solution {solution_id} not found")
        # Refuse before any sandbox-budget accounting: a verified outcome on
        # a demoted solution is as invisible as an observed one (see the
        # demoted guard in report_outcome).
        if solution.promotion_status == "demoted":
            return {
                "status": "not_verifiable",
                "reason": (
                    "solution is demoted and cannot be re-promoted; "
                    "verify its parent instead"
                ),
            }
        problem = self._problems.get(solution.problem_id)
        if problem is None or not problem.error_signature:
            return {
                "status": "not_verifiable",
                "reason": "problem has no error_signature",
            }
        sandbox_available = self._sandbox is not None and not _is_noop_sandbox(
            self._sandbox
        )
        if not sandbox_available:
            return {
                "status": "unavailable",
                "reason": "no sandbox provider configured",
            }
        run_id = uuid4()
        self._run_sandbox_evaluation(problem, solution, agent_id=agent_id)
        return {"status": "queued", "run_id": str(run_id)}

    def _improve_solution_impl(
        self,
        author_id: UUID,
        solution_id: UUID,
        improved_content: str,
        improved_steps: list[str] | None = None,
        reasoning: str = "",
        llm_model: str | None = None,
        root_cause_pattern: str | None = None,
        localization_cues: list[str] | None = None,
        verification: list[dict] | None = None,
    ) -> dict:
        existing = self._solutions.get(solution_id)
        if existing is None:
            raise NotFoundError(f"Solution {solution_id} not found")

        # A demoted solution is a rejected dead end — improving it would spawn
        # a new candidate off a branch the gate already turned down. Direct
        # the caller to the parent instead (matches the demotion message).
        if existing.promotion_status == "demoted":
            raise ValueError(
                "cannot improve a demoted solution: improve its parent or "
                "collect outcome reports on the parent instead"
            )

        # Quality gate — content regression bypasses the gate (evaluate_improvement
        # will reject it with reason "content_regression" instead of raising).
        gate_result = check_spam(
            improved_content,
            "solution",
            {"steps": improved_steps} if improved_steps else None,
        )
        if not gate_result.passed:
            # A secret must never be persisted — not even as the demoted
            # lineage row created further down (lineage rows stay publicly
            # reachable via the timeline).
            if gate_result.reason == "secret_detected":
                raise ValueError(gate_result.detail or gate_result.reason)
            tmp = Solution(
                problem_id=existing.problem_id,
                author_id=author_id,
                content=improved_content,
                steps=improved_steps or [],
            )
            if not is_content_regression(existing, tmp):
                raise ValueError("solution_quality_check_failed")

        # Caller-supplied structured knowledge bypasses the content gate above.
        # Scan it so an improvement cannot smuggle a credential into a publicly
        # readable field; inherited values (caller passed None) were already
        # gated when the parent was created.
        struct_label = detect_secret_in(
            root_cause_pattern, localization_cues, verification
        )
        if struct_label is not None:
            raise ValueError(secret_rejection(struct_label).detail)

        problem = self._problems.get(existing.problem_id)
        if problem is None:
            raise NotFoundError(f"Problem {existing.problem_id} not found")

        self._validate_no_lineage_cycle(solution_id)

        resolved_llm = self._llm_model_for_author(author_id, llm_model)
        new_solution = Solution(
            problem_id=existing.problem_id,
            author_id=author_id,
            content=improved_content,
            steps=improved_steps or [],
            parent_solution_id=solution_id,
            # Mirror create_solution(): a gate-passing proposal is approved.
            # Without this an accepted candidate is later invisible to the
            # get_agentbook review_status=="approved" filter even once
            # outcome reports promote it.
            review_status="approved",
            llm_model=resolved_llm,
            # Inherit the parent's structured knowledge when the caller does not
            # override it, so an improvement refines rather than drops it.
            root_cause_pattern=root_cause_pattern
            if root_cause_pattern is not None
            else existing.root_cause_pattern,
            localization_cues=localization_cues
            if localization_cues is not None
            else list(existing.localization_cues),
            verification=verification
            if verification is not None
            else list(existing.verification),
        )
        self._solutions.add(new_solution)

        previous_best = problem.best_confidence
        new_confidence = new_solution.confidence

        # Sandbox is the primary signal when the problem has a codifiable
        # error_signature AND a real SandboxProvider is configured.
        evaluator_score: float | None = None
        sandbox_score: float | None = None
        sandbox_available = self._sandbox is not None and not _is_noop_sandbox(
            self._sandbox
        )
        problem_has_error_signature = bool(problem.error_signature)

        if problem_has_error_signature and sandbox_available:
            sandbox_score = self._get_sandbox_score(
                problem, existing, new_solution, agent_id=author_id
            )

        # Cold-start evaluator only runs when sandbox is NOT decisive.
        is_cold_start = (
            existing.outcome_count == 0
            and new_solution.confidence == existing.confidence
        )
        if is_cold_start and sandbox_score is None:
            evaluator_score = self._get_llm_evaluation_score(
                problem, existing, new_solution
            )

        accepted, reason = evaluate_improvement(
            existing,
            new_solution,
            evaluator_score=evaluator_score,
            sandbox_score=sandbox_score,
            problem_has_error_signature=problem_has_error_signature,
            sandbox_available=sandbox_available,
        )

        if accepted:
            new_solution.promotion_status = "candidate"
            self._solutions.update(new_solution)
            # solution_count tracks visible solutions only — a pending
            # candidate is not one yet; report_outcome bumps the count if
            # and when the candidate is promoted.
            status = "improved"

            # Record the pre-computed evaluator score as outcome, or run fresh
            # evaluation for non-cold-start acceptances.
            if evaluator_score is not None:
                self._record_synthetic_outcome(
                    new_solution,
                    EVALUATOR_AGENT_ID,
                    success=evaluator_score > 0.5,
                    notes="llm_evaluation",
                )
            else:
                self._run_llm_evaluation(problem, existing, new_solution)

            # Post-acceptance: run sandbox to generate real outcome data.
            if self._sandbox is not None:
                self._run_sandbox_evaluation(problem, new_solution, agent_id=author_id)
        else:
            new_solution.canonical_id = solution_id
            new_solution.promotion_status = "demoted"
            self._solutions.update(new_solution)
            # A demoted proposal is never a visible solution — leave
            # solution_count untouched.
            status = "no_improvement"

        if self._research_cycles is not None:
            cycle = ResearchCycle(
                problem_id=existing.problem_id,
                researcher_id=author_id,
                proposed_solution_id=new_solution.solution_id,
                previous_best_confidence=previous_best,
                new_confidence=new_confidence,
                status=status,
                reasoning=reasoning,
                llm_model=resolved_llm,
            )
            self._research_cycles.add(cycle)

        return {
            "status": status,
            "accepted": accepted,
            "solution_id": new_solution.solution_id,
            "candidate_status": new_solution.promotion_status,
            "previous_confidence": existing.confidence,
            "previous_problem_best": previous_best,
            "new_confidence": new_confidence,
            "reason": reason,
            "next_action": _improvement_next_action(reason, accepted),
            "detail": _improvement_detail(
                accepted=accepted,
                reason=reason,
                candidate_id=new_solution.solution_id,
                parent_id=solution_id,
            ),
        }

    def _ensure_synthetic_agent(self, agent_id: UUID, label: str) -> None:
        """Register a synthetic agent row if missing (FK requirement)."""
        if agent_id in self._synthetic_agents_ensured:
            return
        if self._agents.get(agent_id) is None:
            self._agents.add(
                Agent(agent_id=agent_id, api_key_hash=label, model_type=label)
            )
        self._synthetic_agents_ensured.add(agent_id)

    def _get_llm_evaluation_score(
        self,
        problem: Problem,
        existing: Solution,
        proposed: Solution,
    ) -> float | None:
        """Run LLM A/B comparison and return score without recording outcome.

        Returns None if evaluator is unavailable or fails.
        Score > 0.5 means proposed is better.
        """
        if self._evaluator is None:
            return None
        try:
            self._ensure_synthetic_agent(EVALUATOR_AGENT_ID, "evaluator")
            return self._evaluator.compare(
                problem_description=problem.description,
                solution_a=existing.content,
                solution_b=proposed.content,
            )
        except Exception:
            logger.warning("LLM evaluation scoring failed", exc_info=True)
            return None

    def _record_synthetic_outcome(
        self,
        solution: Solution,
        reporter_id: UUID,
        success: bool,
        weight: float = 0.3,
        notes: str = "",
        environment: dict | None = None,
        kind: OutcomeKind = "observed",
    ) -> None:
        """Record an automated-evaluator outcome.

        Defaults are calibrated for the LLM A/B evaluator (weak signal).
        The sandbox path overrides to ``kind="verified", weight=1.0``.
        """
        try:
            self._ensure_synthetic_agent(reporter_id, reporter_id.hex[:8])
            synthetic = Outcome(
                solution_id=solution.solution_id,
                reporter_id=reporter_id,
                success=success,
                kind=kind,
                weight=weight,
                notes=notes,
                environment=environment,
            )
            self._outcomes.add(synthetic)
            _increment_outcome_counters(solution, success)
            self._solutions.update(solution)
        except Exception:
            logger.warning("Synthetic outcome recording failed", exc_info=True)

    def _run_llm_evaluation(
        self,
        problem: Problem,
        existing: Solution,
        proposed: Solution,
    ) -> None:
        """Run LLM A/B comparison and record result as a synthetic outcome."""
        score = self._get_llm_evaluation_score(problem, existing, proposed)
        if score is not None:
            self._record_synthetic_outcome(
                proposed,
                EVALUATOR_AGENT_ID,
                success=score > 0.5,
                notes="llm_evaluation",
            )

    # ------------------------------------------------------------------
    # Sandbox execution helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_executable_code(solution: Solution) -> str | None:
        """Extract fenced Python code blocks from a solution.

        Only Python blocks are sandbox-executable; shell/prose is skipped.
        """

        blocks = re.findall(
            r"```(?:python|py)?\s*\n(.*?)```",
            solution.content,
            re.DOTALL,
        )
        if blocks:
            return "\n\n".join(block.strip() for block in blocks)
        return None

    def _bump_health_counter(self, key: str) -> None:
        self._health_counters[key] = self._health_counters.get(key, 0) + 1

    def _sandbox_run_guarded(
        self,
        code: str,
        *,
        agent_id: UUID,
        error_signature: str | None,
        environment: dict | None,
    ):
        """Execute code via the sandbox with DoS gates around the call.

        Returns ``SandboxResult`` on success, ``None`` when any gate blocks
        the call. Records circuit-breaker outcomes so repeated container
        errors trip the breaker. Increments observability counters for each
        gate that fires.
        """
        if not self._sandbox_breaker.should_allow():
            self._bump_health_counter("sandbox_circuit_open")
            return None
        if not self._sandbox_budget.try_consume(agent_id):
            self._bump_health_counter("sandbox_budget_exhausted")
            return None
        with self._sandbox_concurrency.guard() as acquired:
            if not acquired:
                self._bump_health_counter("sandbox_concurrency_rejection")
                return None
            try:
                result = self._sandbox.execute(
                    code,
                    error_signature=error_signature,
                    timeout_seconds=settings.sandbox_timeout_seconds,
                    environment=environment,
                )
            except Exception:
                self._sandbox_breaker.record("container_error")
                self._bump_health_counter("sandbox_timeout")
                logger.warning("Sandbox call raised", exc_info=True)
                return None

        # exit_code -1 is the convention for container-side failure
        # (timeout, missing interpreter, container error) versus a real
        # sandbox_fail verdict from a non-zero return.
        is_container_error = result.exit_code == -1
        if is_container_error:
            self._sandbox_breaker.record("container_error")
            self._bump_health_counter("sandbox_timeout")
            return None
        self._sandbox_breaker.record("success" if result.success else "sandbox_fail")
        return result

    def _sandbox_score_with_dedup(
        self,
        code: str,
        *,
        agent_id: UUID,
        error_signature: str | None,
        environment: dict | None,
        success_score: float,
        failure_score: float,
    ) -> float | None:
        """Wrap _sandbox_run_guarded with dedup-cache keyed on (code, sig)."""
        cached = self._sandbox_dedup.get(code, error_signature)
        if cached is not None:
            self._bump_health_counter("sandbox_dedup_hit")
            return cached.sandbox_score
        result = self._sandbox_run_guarded(
            code,
            agent_id=agent_id,
            error_signature=error_signature,
            environment=environment,
        )
        if result is None:
            return None
        score = success_score if result.success else failure_score
        self._sandbox_dedup.put(
            code,
            error_signature,
            sandbox_score=score,
            success=result.success,
        )
        return score

    def _get_sandbox_score(
        self,
        problem: Problem,
        existing: Solution,
        proposed: Solution,
        *,
        agent_id: UUID,
    ) -> float | None:
        """Run both solutions in sandbox, return >0.5 if proposed is better.

        Returns None if neither solution contains executable code, or if
        every relevant sandbox call was blocked by a DoS gate.
        """
        existing_code = self._extract_executable_code(existing)
        proposed_code = self._extract_executable_code(proposed)

        if existing_code is None and proposed_code is None:
            return None

        env = problem.environment
        sig = problem.error_signature

        # Proposed has code but existing doesn't: proposed wins if it runs.
        if existing_code is None and proposed_code is not None:
            return self._sandbox_score_with_dedup(
                proposed_code,
                agent_id=agent_id,
                error_signature=sig,
                environment=env,
                success_score=0.8,
                failure_score=0.3,
            )

        # Existing has code but proposed doesn't: existing wins.
        if existing_code is not None and proposed_code is None:
            return 0.2

        # Both have code: run both and compare.
        existing_result = self._sandbox_run_guarded(
            existing_code,
            agent_id=agent_id,
            error_signature=sig,
            environment=env,
        )
        proposed_result = self._sandbox_run_guarded(
            proposed_code,
            agent_id=agent_id,
            error_signature=sig,
            environment=env,
        )
        if existing_result is None or proposed_result is None:
            return None

        if proposed_result.success and not existing_result.success:
            return 0.9
        if not proposed_result.success and existing_result.success:
            return 0.1
        if proposed_result.success and existing_result.success:
            # Both succeed -- slight preference for faster execution.
            if (
                proposed_result.duration_seconds
                < existing_result.duration_seconds * 0.8
            ):
                return 0.6
            return 0.5
        # Both fail.
        return 0.5

    def _run_sandbox_evaluation(
        self,
        problem: Problem,
        solution: Solution,
        *,
        agent_id: UUID,
    ) -> None:
        """Run a solution in the sandbox and record the outcome.

        Skips outcome recording when a DoS gate blocks the call -- the
        gate already incremented its observability counter.
        """
        code = self._extract_executable_code(solution)
        if code is None:
            return

        result = self._sandbox_run_guarded(
            code,
            agent_id=agent_id,
            error_signature=problem.error_signature,
            environment=problem.environment,
        )
        if result is None:
            return
        self._record_synthetic_outcome(
            solution,
            SANDBOX_AGENT_ID,
            success=result.success,
            kind="verified",
            weight=1.0,
            notes=f"sandbox: exit={result.exit_code} dur={result.duration_seconds}s",
            environment=result.environment or None,
        )

    # ------------------------------------------------------------------
    # Cross-problem knowledge graph helpers
    # ------------------------------------------------------------------

    def _compute_relationships(self, problem: Problem) -> None:
        """Recompute all outgoing relationships for a problem.

        Called after embedding generation when knowledge_graph_enabled.
        Creates vector_similarity, error_signature, and tag_overlap links.
        """
        if self._problem_relationships is None:
            return

        self._problem_relationships.delete_by_source(problem.problem_id)

        max_rels = settings.knowledge_graph_max_relationships
        min_sim = settings.knowledge_graph_min_similarity
        added = 0

        # 1. Vector similarity relationships.
        if problem.embedding is not None:
            scored = self._problems.find_similar_scored(problem.embedding)
            for other, sim in scored:
                if other.problem_id == problem.problem_id:
                    continue
                if sim < min_sim:
                    break
                if added >= max_rels:
                    break
                self._problem_relationships.add(
                    ProblemRelationship(
                        source_problem_id=problem.problem_id,
                        target_problem_id=other.problem_id,
                        relationship_type="vector_similarity",
                        score=sim,
                    )
                )
                added += 1

        # 2+3. Error signature and tag overlap (single pass over all problems).
        needs_errsig = bool(problem.error_signature)
        errsig_prefix = problem.error_signature.split(":")[0] if needs_errsig else ""
        needs_tags = bool(problem.tags)
        source_tags = set(problem.tags) if needs_tags else set()

        if needs_errsig or needs_tags:
            all_problems = self._problems.list_all()
            for other in all_problems:
                if other.problem_id == problem.problem_id:
                    continue
                if added >= max_rels:
                    break

                if (
                    needs_errsig
                    and other.error_signature
                    and other.error_signature.split(":")[0] == errsig_prefix
                ):
                    self._problem_relationships.add(
                        ProblemRelationship(
                            source_problem_id=problem.problem_id,
                            target_problem_id=other.problem_id,
                            relationship_type="error_signature",
                            score=0.7,
                        )
                    )
                    added += 1
                    if added >= max_rels:
                        break

                if needs_tags and other.tags:
                    target_tags = set(other.tags)
                    intersection = len(source_tags & target_tags)
                    union = len(source_tags | target_tags)
                    if union > 0:
                        jaccard = intersection / union
                        if jaccard > 0.3:
                            self._problem_relationships.add(
                                ProblemRelationship(
                                    source_problem_id=problem.problem_id,
                                    target_problem_id=other.problem_id,
                                    relationship_type="tag_overlap",
                                    score=round(jaccard, 3),
                                )
                            )
                            added += 1

    def get_cross_problem_solutions(
        self,
        problem_id: UUID,
        limit: int = 5,
    ) -> list[dict]:
        """Get solutions from related problems for cross-problem context.

        Returns a list of dicts with relationship metadata and solution previews
        from problems related to the given problem_id.
        """
        if self._problem_relationships is None:
            return []

        related = self._problem_relationships.find_related(
            problem_id, min_score=0.5, limit=limit * 2
        )

        results: list[dict] = []
        for rel in related:
            if len(results) >= limit:
                break
            target_problem = self._problems.get(rel.target_problem_id)
            if target_problem is None:
                continue
            # Canonical visibility filter: cross-problem surfacing must not leak
            # an unpromoted candidate or demoted proposal from a related problem,
            # matching search/trace/agentbook.
            solutions = [
                s
                for s in self._solutions.list_by_problem(rel.target_problem_id)
                if _is_visible_solution(s)
            ]
            if not solutions:
                continue
            best = max(solutions, key=lambda s: s.confidence)
            if best.confidence < 0.3:
                continue
            results.append(
                {
                    "from_problem_id": str(rel.target_problem_id),
                    "relationship_type": rel.relationship_type,
                    "relationship_score": rel.score,
                    "solution_content_preview": best.content[:300],
                    "confidence": best.confidence,
                }
            )

        return results

    def synthesize_solutions(
        self,
        problem_id: UUID,
        synthesized_content: str | None = None,
        author_id: UUID | None = None,
        llm_model: str | None = None,
        synthesized_root_cause_pattern: str | None = None,
        synthesized_localization_cues: list[str] | None = None,
        synthesized_verification: list[dict] | None = None,
        synthesized_root_cause_class: str | None = None,
    ) -> dict | None:
        """Create a canonical solution synthesized from multiple active solutions.

        Marks source solutions as superseded, updates problem.best_confidence.
        Returns None if fewer than 2 active solutions exist.
        """
        problem = self._problems.get(problem_id)
        if problem is None:
            raise NotFoundError(f"Problem {problem_id} not found")

        all_solutions = self._solutions.list_by_problem(problem_id)
        # Active = non-superseded AND validated (visible). A pending candidate or
        # demoted proposal must not count toward the >=2 gate nor have its
        # unvalidated content merged into the canonical solution (and then be
        # frozen as superseded) — synthesis distils proven solutions only.
        active = [
            s
            for s in all_solutions
            if s.canonical_id is None and _is_visible_solution(s)
        ]
        if len(active) < 2:
            return None

        total_outcomes = sum(s.outcome_count for s in active)
        total_successes = sum(s.success_count for s in active)
        total_failures = sum(s.failure_count for s in active)

        _author_id = author_id or UUID("00000000-0000-0000-0000-000000000001")
        _all_outcomes = [
            o for s in active for o in self._outcomes.list_by_solution(s.solution_id)
        ]
        num_effective = _count_effective_reporters(
            _all_outcomes, self._agents, _author_id
        )
        confidence = calculate_confidence(
            _all_outcomes,
            _author_id,
            num_effective_reporters=num_effective,
        )
        if synthesized_content is None:
            synthesized_content = "\n\n".join(
                f"Solution {i + 1}:\n{s.content}" for i, s in enumerate(active[:5])
            )

        gate_result = check_spam(synthesized_content, "solution")
        if not gate_result.passed:
            synthesized_content = (
                active[0].content if active else "Synthesized solution"
            )

        # Carry the structured, weak-model-actionable knowledge forward into the
        # canonical solution instead of dropping it: the root-cause pattern from
        # the highest-confidence source that has one, plus the union of
        # localization cues and verification repros across the synthesized sources.
        ranked = sorted(active, key=lambda s: s.confidence, reverse=True)
        merged_root_cause = next(
            (s.root_cause_pattern for s in ranked if s.root_cause_pattern), None
        )
        merged_root_cause_class = next(
            (s.root_cause_class for s in ranked if s.root_cause_class), None
        )
        merged_cues: list[str] = []
        for s in ranked:
            for cue in s.localization_cues:
                if cue not in merged_cues:
                    merged_cues.append(cue)
        merged_verification: list[dict] = []
        seen_cmds: set[str] = set()
        for s in ranked:
            for v in s.verification:
                cmd = v.get("command") if isinstance(v, dict) else None
                if cmd is None or cmd not in seen_cmds:
                    merged_verification.append(v)
                    if cmd is not None:
                        seen_cmds.add(cmd)

        # An LLM synthesis pass that distils the sources can hand us freshly
        # generated structured knowledge; prefer it over the mechanical union
        # so the canonical entry reflects the synthesised pattern, not a pile of
        # per-source notes. Fall back to the merge when a field is not supplied.
        final_root_cause = (
            synthesized_root_cause_pattern
            if synthesized_root_cause_pattern is not None
            else merged_root_cause
        )
        final_cues = (
            synthesized_localization_cues
            if synthesized_localization_cues is not None
            else merged_cues
        )
        final_verification = (
            synthesized_verification
            if synthesized_verification is not None
            else merged_verification
        )
        final_root_cause_class = (
            synthesized_root_cause_class
            if synthesized_root_cause_class is not None
            else merged_root_cause_class
        )

        canonical = Solution(
            problem_id=problem_id,
            author_id=_author_id,
            content=synthesized_content,
            outcome_count=total_outcomes,
            success_count=total_successes,
            failure_count=total_failures,
            llm_model=self._llm_model_for_author(_author_id, llm_model),
            root_cause_pattern=final_root_cause,
            localization_cues=final_cues,
            verification=final_verification,
            root_cause_class=final_root_cause_class,
        )
        canonical.confidence = max(confidence, canonical.confidence)
        canonical.review_status = "approved"
        self._solutions.add(canonical)

        for s in active:
            s.canonical_id = canonical.solution_id
            self._solutions.update(s)

        problem.canonical_solution_id = canonical.solution_id
        if canonical.confidence > problem.best_confidence:
            problem.best_confidence = canonical.confidence
        # Mirror the root-cause class onto the problem as a pattern:<slug> tag so
        # cross-task retrieval can match this problem from a sibling's query.
        if final_root_cause_class:
            pattern_tag = f"{_PATTERN_TAG_PREFIX}{final_root_cause_class}"
            tags = list(problem.tags or [])
            if pattern_tag not in tags:
                tags.append(pattern_tag)
                problem.tags = tags
        self._problems.update(problem)

        # Synthesis adds the canonical solution and supersedes its sources —
        # both change what search returns.
        self._invalidate_search_cache()

        return {
            "canonical_solution_id": canonical.solution_id,
            "synthesized_from": len(active),
            "confidence": canonical.confidence,
        }

    def _has_pending_candidate(self, problem_id: UUID) -> bool:
        """True when the problem has an unvalidated candidate solution.

        A ``candidate`` is a proposed improvement awaiting outcome reports; it
        is promoted or demoted once external reporters weigh in. While one is
        pending, the problem is "awaiting outcomes" -- not a research candidate.
        """
        return any(
            s.promotion_status == "candidate"
            for s in self._solutions.list_by_problem(problem_id)
        )

    def find_research_candidates(
        self,
        limit: int = 10,
        cooldown_hours: int = 0,
        max_confidence: float = 0.85,
        stall_threshold: int = 3,
        min_solution_count: int = 0,
    ) -> list[dict]:
        needs_filtering = (
            cooldown_hours > 0 or stall_threshold > 0
        ) and self._research_cycles is not None
        if not needs_filtering:
            candidates = self._problems.find_research_candidates(
                limit=limit,
                max_confidence=max_confidence,
                min_solution_count=min_solution_count,
            )
            cids = {p.author_id for p in candidates}
            cmap = self._agent_models_map(cids)
            return [
                {
                    **_problem_to_dict(p),
                    "llm_model": self._display_llm(cmap, p.author_id, None),
                }
                for p in candidates
            ]
        cutoff = (
            utc_now() - timedelta(hours=cooldown_hours) if cooldown_hours > 0 else None
        )
        page_size = max(limit, 10)
        offset = 0
        filtered: list = []
        while len(filtered) < limit:
            batch = self._problems.find_research_candidates(
                limit=page_size,
                offset=offset,
                max_confidence=max_confidence,
                min_solution_count=min_solution_count,
            )
            if not batch:
                break
            for p in batch:
                if cutoff is not None:
                    last = self._research_cycles.get_last_researched_at(p.problem_id)
                    if last is not None and last >= cutoff:
                        continue
                if stall_threshold > 0:
                    stalled = self._research_cycles.count_consecutive_no_improvement(
                        p.problem_id
                    )
                    if stalled >= stall_threshold:
                        continue
                # Information-triggered scheduling: a problem that already carries an
                # unvalidated candidate has a proposed improvement awaiting outcome
                # reports. Proposing another before it is promoted/demoted is churn --
                # the improve-only loop otherwise piles a fresh candidate on every
                # cooldown with nothing able to promote it. Skip until an outcome
                # resolves the candidate, which makes the problem eligible again.
                if self._has_pending_candidate(p.problem_id):
                    continue
                filtered.append(p)
                if len(filtered) >= limit:
                    break
            offset += page_size
        fids = {p.author_id for p in filtered}
        fmap = self._agent_models_map(fids)
        return [
            {
                **_problem_to_dict(p),
                "llm_model": self._display_llm(fmap, p.author_id, None),
            }
            for p in filtered
        ]

    def set_research_status(self, problem_id: UUID, is_researching: bool) -> None:
        """Mark a problem as actively being researched (or clear the flag)."""
        problem = self._problems.get(problem_id)
        if problem is None:
            return
        problem.research_started_at = utc_now() if is_researching else None
        # Bypass optimistic locking version check: use a direct field update
        # by re-fetching so our version matches current state.
        current = self._problems.get(problem_id)
        if current is None:
            return
        current.research_started_at = problem.research_started_at
        self._problems.update(current)

    def record_research_skip(
        self,
        problem_id: UUID,
        researcher_id: UUID,
        reasoning: str = "",
        status: ResearchStatus = "no_improvement",
        llm_model: str | None = None,
    ) -> None:
        if self._research_cycles is None:
            return
        problem = self._problems.get(problem_id)
        if problem is None:
            return
        cycle = ResearchCycle(
            problem_id=problem_id,
            researcher_id=researcher_id,
            proposed_solution_id=None,
            previous_best_confidence=problem.best_confidence,
            new_confidence=problem.best_confidence,
            status=status,
            reasoning=reasoning,
            llm_model=self._llm_model_for_author(researcher_id, llm_model),
        )
        self._research_cycles.add(cycle)

    def get_solution_lineage(self, solution_id: UUID) -> list[dict]:
        solution = self._solutions.get(solution_id)
        if solution is None or solution.review_status == "removed":
            raise NotFoundError(f"Solution {solution_id} not found")

        chain: list[Solution] = [solution]
        visited: set[UUID] = {solution_id}
        current = solution
        while (
            current.parent_solution_id is not None
            and current.parent_solution_id not in visited
        ):
            parent = self._solutions.get(current.parent_solution_id)
            if parent is None:
                break
            visited.add(parent.solution_id)
            chain.append(parent)
            current = parent

        chain.reverse()
        ids = {s.author_id for s in chain}
        models = self._agent_models_map(ids)
        return [_solution_to_dict(s, models.get(s.author_id)) for s in chain]

    def takedown_problem(self, problem_id: UUID) -> dict:
        """Operator-only remediation: redact a problem and all its solutions.

        Clears every contributor-supplied field that could carry a leaked
        credential (description, error_signature, environment, tags) and the
        embedding derived from them; ``review_status='removed'`` drops the
        problem out of every public read path.
        """
        problem = self._problems.get(problem_id)
        if problem is None:
            raise NotFoundError(f"Problem {problem_id} not found")
        problem.description = _REDACTED_PLACEHOLDER
        problem.error_signature = None
        problem.environment = None
        problem.tags = []
        problem.embedding = None
        problem.review_status = "removed"
        self._problems.update(problem)
        solutions = self._solutions.list_by_problem(problem_id)
        for solution in solutions:
            self._redact_solution(solution)
        self._invalidate_search_cache()
        return {
            "status": "removed",
            "problem_id": str(problem_id),
            "solutions_redacted": len(solutions),
        }

    def takedown_solution(self, solution_id: UUID) -> dict:
        """Operator-only remediation: redact a single solution in place."""
        solution = self._solutions.get(solution_id)
        if solution is None:
            raise NotFoundError(f"Solution {solution_id} not found")
        self._redact_solution(solution)
        self._invalidate_search_cache()
        return {"status": "removed", "solution_id": str(solution_id)}

    def _redact_solution(self, solution: Solution) -> None:
        solution.content = _REDACTED_PLACEHOLDER
        solution.steps = []
        solution.root_cause_pattern = None
        solution.localization_cues = []
        solution.verification = []
        solution.review_status = "removed"
        self._solutions.update(solution)

    def get_research_history(self, problem_id: UUID) -> list[dict]:
        if self._research_cycles is None:
            return []
        cycles = self._research_cycles.list_by_problem(problem_id)
        ids = {c.researcher_id for c in cycles}
        models = self._agent_models_map(ids)
        return [_research_cycle_to_dict(c, models.get(c.researcher_id)) for c in cycles]

    def get_problem(self, problem_id: UUID) -> Problem | None:
        return self._problems.get(problem_id)

    def list_outcomes_for_solution(self, solution_id: UUID) -> list[Outcome]:
        return self._outcomes.list_by_solution(solution_id)

    def list_outcomes_by_reporter(
        self, reporter_id: UUID, since: datetime | None = None
    ) -> list[Outcome]:
        outcomes = self._outcomes.list_by_reporter(reporter_id)
        if since is None:
            return outcomes
        return [o for o in outcomes if o.created_at >= since]

    def get_health_counters(self) -> dict[str, int]:
        return dict(self._health_counters)

    def get_retrieval_status(self) -> tuple[str, bool]:
        """Pass-through to ``ProblemRepository.retrieval_status``.

        Lets the health endpoint surface backend identity + pgvector
        availability without reaching across the application layer
        into a private repository attribute.
        """
        return self._problems.retrieval_status()

    def get_failed_approaches(
        self, problem_id: UUID, stall_threshold: int, limit: int = 5
    ) -> tuple[list[str], bool]:
        """Return (failed approach reasonings, radical_mode flag) for a problem."""
        if self._research_cycles is None:
            return [], False
        recent_cycles = self._research_cycles.list_by_problem(problem_id)[:limit]
        failed = [
            c.reasoning for c in recent_cycles if c.status != "improved" and c.reasoning
        ]
        stalled = self._research_cycles.count_consecutive_no_improvement(problem_id)
        return failed, stalled >= stall_threshold

    def count_consecutive_no_improvement(self, problem_id: UUID) -> int:
        """Return the consecutive no-improvement streak for a problem."""
        if self._research_cycles is None:
            return 0
        return self._research_cycles.count_consecutive_no_improvement(problem_id)

    def record_research_cycle(self, cycle: ResearchCycle) -> None:
        """Persist a research cycle (noop when research history is disabled)."""
        if self._research_cycles is None:
            return
        self._research_cycles.add(cycle)

    def _resolve_book_solution(
        self,
        problem: Problem,
        all_solutions: list[Solution],
        models: dict,
        system_agent_id: UUID,
    ) -> dict | None:
        """Single source of truth for the Solution panel: DB canonical pointer first, then fallbacks.

        Mirrors the former client pickBestEntry order but never disagrees with ``canonical_solution_id``.
        """

        def serialize(s: Solution) -> dict:
            is_syn = (
                problem.canonical_solution_id is not None
                and s.solution_id == problem.canonical_solution_id
                and s.author_id == system_agent_id
                and s.parent_solution_id is None
            )
            stored_llm = s.llm_model
            return {
                "solution_id": str(s.solution_id),
                "author_id": str(s.author_id),
                "content": s.content,
                "steps": s.steps,
                "root_cause_pattern": s.root_cause_pattern,
                "localization_cues": s.localization_cues,
                "verification": s.verification,
                "root_cause_class": s.root_cause_class,
                "confidence": s.confidence,
                "promotion_status": s.promotion_status,
                "outcome_count": s.outcome_count,
                "success_count": s.success_count,
                "failure_count": s.failure_count,
                "llm_model": self._display_llm(models, s.author_id, stored_llm),
                "created_at": s.created_at.isoformat(),
                "is_synthesized": is_syn,
            }

        if not all_solutions:
            return None

        if problem.canonical_solution_id:
            s = self._solutions.get(problem.canonical_solution_id)
            if s is not None:
                return serialize(s)

        promoted = [
            s
            for s in all_solutions
            if s.parent_solution_id is not None and s.promotion_status == "promoted"
        ]
        promoted.sort(key=lambda x: x.confidence, reverse=True)
        if promoted:
            return serialize(promoted[0])

        roots: list[Solution] = []
        for s in all_solutions:
            if s.parent_solution_id is not None:
                continue
            if s.promotion_status == "demoted":
                continue
            roots.append(s)
        roots.sort(key=lambda x: x.confidence, reverse=True)
        if roots:
            return serialize(roots[0])

        improved = [s for s in all_solutions if s.parent_solution_id is not None]
        improved.sort(key=lambda x: x.confidence, reverse=True)
        if improved:
            return serialize(improved[0])

        fallback = sorted(all_solutions, key=lambda x: x.confidence, reverse=True)
        if fallback:
            return serialize(fallback[0])
        return None

    def _reliance_confidence_note(self, solution: Solution) -> str:
        """Read-surface note explaining where the solution's confidence sits.

        Reuses the same ``_confidence_explainer`` the write path uses so a
        reader sees the identical cold-start / author-self-report wording the
        reporter would. No new math — the confidence is read off the solution
        and the effective external reporter count is recomputed from outcomes.
        """
        outcomes = self._outcomes.list_by_solution(solution.solution_id)
        num_effective = _count_effective_reporters(
            outcomes, self._agents, solution.author_id
        )
        capped = (
            num_effective < COLD_START_MIN_REPORTERS
            and solution.confidence >= COLD_START_FLOOR
        )
        return _confidence_explainer(
            new_confidence=solution.confidence,
            previous_confidence=solution.confidence,
            external_reporters=num_effective,
            capped=capped,
            outcome_success=True,
        )

    def _resolve_reliance_target(self, problem_id: UUID) -> dict | None:
        """The one solution a reading agent should rely on, on every surface.

        Canonical (synthesized) solution when synthesis has run; otherwise the
        highest-confidence active solution as a self-described cold-start
        fallback. The returned row carries ``is_synthesized``, a ``note`` that
        explains the fallback, and a ``confidence_note`` mirroring the write
        path's cold-start explanation — so GET problem, MCP trace and the
        timeline all agree on what to rely on and why.
        """
        SYSTEM_AGENT_ID = UUID("00000000-0000-0000-0000-000000000001")
        problem = self._problems.get(problem_id)
        if problem is None:
            return None
        all_solutions = self._solutions.list_by_problem(problem_id)
        agent_ids: set[UUID] = {s.author_id for s in all_solutions}
        models = self._agent_models_map(agent_ids)
        target = self._resolve_book_solution(
            problem, all_solutions, models, SYSTEM_AGENT_ID
        )
        if target is None:
            return None
        solution = self._solutions.get(UUID(target["solution_id"]))
        if target["is_synthesized"]:
            target["note"] = (
                "This is the synthesized canonical solution: the research agent "
                "merged the problem's solutions into one entry."
            )
        else:
            target["note"] = (
                "No synthesis pass has run, so rely on the highest-confidence "
                "active solution until synthesis produces a canonical entry."
            )
        if solution is not None:
            target["confidence_note"] = self._reliance_confidence_note(solution)
        return target

    def get_problem_timeline(self, problem_id: UUID) -> dict:
        SYSTEM_AGENT_ID = UUID("00000000-0000-0000-0000-000000000001")

        problem = self._problems.get(problem_id)
        if problem is None or problem.review_status == "removed":
            raise NotFoundError(f"Problem {problem_id} not found")

        all_solutions = self._solutions.list_by_problem(problem_id)

        research_cycles: list[ResearchCycle] = []
        if self._research_cycles is not None:
            research_cycles = self._research_cycles.list_by_problem(problem_id)

        solution_ids = [s.solution_id for s in all_solutions]
        all_outcomes: list[Outcome] = []
        if self._outcomes is not None and solution_ids:
            all_outcomes = self._outcomes.list_by_problem(problem_id, solution_ids)

        # Build index: proposed_solution_id -> ResearchCycle (for merge)
        cycle_by_solution: dict[UUID, ResearchCycle] = {
            c.proposed_solution_id: c
            for c in research_cycles
            if c.proposed_solution_id is not None
        }

        agent_ids: set[UUID] = {problem.author_id}
        for s in all_solutions:
            agent_ids.add(s.author_id)
        for o in all_outcomes:
            agent_ids.add(o.reporter_id)
        for c in research_cycles:
            agent_ids.add(c.researcher_id)
        models = self._agent_models_map(agent_ids)

        events: list[dict] = []

        # Event: problem_created
        events.append(
            {
                "event_type": "problem_created",
                "created_at": problem.created_at.isoformat(),
                "author_id": str(problem.author_id),
                "llm_model": self._display_llm(models, problem.author_id, None),
                "description": problem.description,
                "tags": problem.tags or [],
                "error_signature": problem.error_signature,
            }
        )

        # Events: solution_proposed / solution_improved / synthesis_created
        for s in all_solutions:
            is_synthesis = (
                s.solution_id == problem.canonical_solution_id
                and s.author_id == SYSTEM_AGENT_ID
                and s.parent_solution_id is None
            )
            if is_synthesis:
                event_type = "synthesis_created"
            elif s.parent_solution_id is not None:
                event_type = "solution_improved"
            else:
                event_type = "solution_proposed"

            cycle = cycle_by_solution.get(s.solution_id)
            stored_llm = s.llm_model or (cycle.llm_model if cycle else None)
            entry: dict = {
                "event_type": event_type,
                "created_at": s.created_at.isoformat(),
                "solution_id": str(s.solution_id),
                "author_id": str(s.author_id),
                "content": s.content,
                "steps": s.steps,
                "confidence": s.confidence,
                "promotion_status": s.promotion_status,
                "canonical_id": str(s.canonical_id) if s.canonical_id else None,
                "parent_solution_id": str(s.parent_solution_id)
                if s.parent_solution_id
                else None,
                "outcome_count": s.outcome_count,
                "success_count": s.success_count,
                "failure_count": s.failure_count,
                "review_status": s.review_status,
                "llm_model": self._display_llm(models, s.author_id, stored_llm),
            }

            if cycle:
                entry["reasoning"] = cycle.reasoning
                entry["confidence_delta"] = round(
                    cycle.new_confidence - cycle.previous_best_confidence, 4
                )
                entry["previous_best_confidence"] = cycle.previous_best_confidence
                entry["research_status"] = cycle.status

            events.append(entry)

        # Events: research_skipped (cycles without a proposed solution)
        for c in research_cycles:
            if c.proposed_solution_id is None:
                events.append(
                    {
                        "event_type": "research_skipped",
                        "created_at": c.created_at.isoformat(),
                        "author_id": str(c.researcher_id),
                        "llm_model": self._display_llm(
                            models, c.researcher_id, c.llm_model
                        ),
                        "reasoning": c.reasoning,
                        "status": c.status,
                        "previous_best_confidence": c.previous_best_confidence,
                    }
                )

        # Events: outcome_reported
        for o in all_outcomes:
            events.append(
                {
                    "event_type": "outcome_reported",
                    "created_at": o.created_at.isoformat(),
                    "author_id": str(o.reporter_id),
                    "llm_model": self._display_llm(models, o.reporter_id, None),
                    "solution_id": str(o.solution_id),
                    "success": o.success,
                    "environment": o.environment,
                    "notes": o.notes,
                    "time_saved_seconds": o.time_saved_seconds,
                    "weight": o.weight,
                }
            )

        events.sort(key=lambda e: e["created_at"])

        # Latest activity = newest timeline event (solutions, outcomes, research, etc.)
        updated_at = (
            events[-1]["created_at"] if events else problem.created_at.isoformat()
        )

        book_solution = self._resolve_book_solution(
            problem, all_solutions, models, SYSTEM_AGENT_ID
        )

        return {
            "problem": {
                "problem_id": str(problem.problem_id),
                "author_id": str(problem.author_id),
                "llm_model": self._display_llm(models, problem.author_id, None),
                "description": problem.description,
                "tags": problem.tags or [],
                "error_signature": problem.error_signature,
                "best_confidence": problem.best_confidence,
                "solution_count": problem.solution_count,
                "created_at": problem.created_at.isoformat(),
                "updated_at": updated_at,
                "has_canonical": problem.canonical_solution_id is not None,
                "canonical_solution_id": str(problem.canonical_solution_id)
                if problem.canonical_solution_id
                else None,
                "is_being_researched": _is_being_researched(problem),
            },
            "book_solution": book_solution,
            "reliance_target": self._resolve_reliance_target(problem_id),
            "timeline": events,
        }


def _is_being_researched(
    problem: Problem, timeout_seconds: int = RESEARCH_TIMEOUT_SECONDS
) -> bool:
    """Return True if research is actively in progress (not stale)."""
    if problem.research_started_at is None:
        return False
    age = (utc_now() - problem.research_started_at).total_seconds()
    return age < timeout_seconds


def _is_visible_solution(s: Solution) -> bool:
    """A solution that belongs in the public agentbook view.

    Approved by the quality gate, and neither an unconfirmed improve
    proposal (``candidate``) nor a rejected one (``demoted``). Shared by
    get_agentbook(), inspect_resource() and the solution_count bookkeeping
    so every surface agrees on what counts as a real solution.
    """
    return s.review_status == "approved" and s.promotion_status not in (
        "candidate",
        "demoted",
    )


def _problem_to_dict(p: Problem) -> dict:
    return {
        "problem_id": p.problem_id,
        "author_id": p.author_id,
        "description": p.description,
        "error_signature": p.error_signature,
        "tags": p.tags or [],
        "best_confidence": p.best_confidence,
        "solution_count": p.solution_count,
        "created_at": p.created_at,
        "canonical_solution_id": p.canonical_solution_id,
        "has_canonical": p.canonical_solution_id is not None,
    }


def _solution_to_dict(s: Solution, author_model: str | None = None) -> dict:
    return {
        "solution_id": s.solution_id,
        "problem_id": s.problem_id,
        "author_id": s.author_id,
        "content": s.content,
        "steps": s.steps,
        "root_cause_pattern": s.root_cause_pattern,
        "localization_cues": s.localization_cues,
        "verification": s.verification,
        "confidence": s.confidence,
        "outcome_count": s.outcome_count,
        "success_count": s.success_count,
        "failure_count": s.failure_count,
        "canonical_id": s.canonical_id,
        "parent_solution_id": s.parent_solution_id,
        "promotion_status": s.promotion_status,
        "review_status": s.review_status,
        "created_at": s.created_at,
        "llm_model": s.llm_model or author_model,
    }


def _research_cycle_to_dict(
    c: ResearchCycle, researcher_model: str | None = None
) -> dict:
    return {
        "cycle_id": c.cycle_id,
        "problem_id": c.problem_id,
        "researcher_id": c.researcher_id,
        "proposed_solution_id": c.proposed_solution_id,
        "previous_best_confidence": c.previous_best_confidence,
        "new_confidence": c.new_confidence,
        "status": c.status,
        "reasoning": c.reasoning,
        "created_at": c.created_at,
        "llm_model": c.llm_model or researcher_model,
    }


def _outcome_to_dict(o: Outcome, reporter_model: str | None = None) -> dict:
    return {
        "outcome_id": o.outcome_id,
        "solution_id": o.solution_id,
        "reporter_id": o.reporter_id,
        "success": o.success,
        "kind": o.kind,
        "environment": o.environment,
        "notes": o.notes,
        "time_saved_seconds": o.time_saved_seconds,
        "weight": o.weight,
        "created_at": o.created_at,
        "llm_model": reporter_model,
    }
