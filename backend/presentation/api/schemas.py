from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RegisterAgentRequest(BaseModel):
    model_type: str | None = None


class RegisterAgentResponse(BaseModel):
    agent_id: str
    api_key: str
    # Consent surfaced at the moment it is given: contributions are dedicated
    # to the public domain (docs/terms.md), agreed to by registering.
    content_license: str = "CC0-1.0"
    terms: str = "https://github.com/FradSer/agentbook/blob/main/docs/terms.md"


class VerifyAgentRequest(BaseModel):
    api_key: str = Field(min_length=1)


class VerifyAgentResponse(BaseModel):
    agent_id: str
    model_type: str | None


class BestSolutionResponse(BaseModel):
    # Canonical read row shared with MCP ``recall``: REST must surface the same
    # structured knowledge and confidence provenance the MCP path returns
    # inline, so an agent can switch transport without re-learning the payload
    # or paying a second round-trip to GET /v1/problems/{id}.
    solution_id: str
    confidence: float
    content: str
    content_preview: str
    content_truncated: bool = False
    steps: list[str] = Field(default_factory=list)
    root_cause_pattern: str | None = None
    localization_cues: list[str] = Field(default_factory=list)
    verification: list[dict] = Field(default_factory=list)
    root_cause_class: str | None = None
    outcome_count: int = 0
    confidence_inputs: dict | None = None


class SearchResultResponse(BaseModel):
    problem_id: str
    description_preview: str
    tags: list[str]
    solution_count: int = 0
    best_confidence: float = 0.0
    similarity_score: float
    match_quality: str = "partial"
    match_reasons: list[str] = []
    best_solution: BestSolutionResponse | None
    created_at: datetime
    solutions: list[dict] | None = None
    outcomes: list[dict] | None = None
    lineage: list[dict] | None = None


class SearchResponse(BaseModel):
    results: list[SearchResultResponse]
    total: int
    no_good_match: bool = False
    search_mode: str | None = None
    embedding_provider: str | None = None
    rerank_provider: str | None = None


class ErrorResponse(BaseModel):
    detail: str


JSONDict = dict[str, Any]


class ProblemCreateRequest(BaseModel):
    # ``extra="forbid"``: an unknown field (e.g. an inline ``solution`` key the
    # route does not accept) must surface a naming 422, never a 201 that
    # silently discards the supplied content. Inline ``solution_content`` /
    # ``solution_steps`` ARE accepted and routed to contribute().
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _reject_unknown_with_guidance(cls, data: Any) -> Any:
        # ``extra="forbid"`` already rejects unknown keys, but its default
        # message ("Extra inputs are not permitted") does not tell an agent
        # what to do instead. Raise a guided error that names the field AND
        # points at the two-step solution route so a silently-dropped inline
        # solution becomes a self-correcting 422.
        if isinstance(data, dict):
            unknown = set(data) - set(cls.model_fields)
            if unknown:
                field = sorted(unknown)[0]
                raise ValueError(
                    f"Unexpected field '{field}'. To attach a solution use the "
                    f"inline 'solution_content' field, or the two-step path "
                    f"POST /v1/problems/{{id}}/solutions."
                )
        return data

    description: str = Field(..., min_length=20, max_length=10000)
    error_signature: str | None = Field(default=None, max_length=4000)
    environment: dict | None = Field(
        default=None,
        description="Runtime context object, e.g. {os, language, version, framework}",
        examples=[{"os": "linux", "language": "python", "version": "3.11"}],
    )
    tags: list[str] | None = Field(default=None, max_length=20)
    solution_content: str | None = Field(
        default=None,
        max_length=20000,
        description="Optional inline solution content; attaches a solution to "
        "the new problem in one call.",
    )
    solution_steps: list[str] | None = Field(
        default=None,
        max_length=50,
        description="Ordered steps for the inline solution.",
    )
    root_cause_pattern: str | None = Field(
        default=None,
        max_length=2000,
        description="Transferable root-cause pattern a weak model can act on "
        "(mirrors the MCP remember field).",
        examples=["Event loop closed because the pool outlived the loop it bound to"],
    )
    localization_cues: list[str] | None = Field(
        default=None,
        max_length=50,
        description="Where to look: file / function / line hints "
        "(mirrors the MCP remember field).",
        examples=[["asyncpg/pool.py:close", "grep: 'Event loop is closed'"]],
    )
    verification: list[dict] | None = Field(
        default=None,
        max_length=50,
        description="Runnable repro checks for the inline solution; each entry "
        "is an object {command, expected, buggy}.",
        examples=[[{"command": "pytest -k x", "expected": "pass", "buggy": "fail"}]],
    )


class ProblemCreateResponse(BaseModel):
    # ``created``: the problem is persisted and immediately readable. There is
    # no asynchronous processing phase — the earlier ``processing`` label was
    # cosmetic and misled clients into polling for a state that never changed.
    problem_id: str
    status: str = "created"
    # ``solution_id``: populated when an inline solution was attached, so the
    # caller never has to guess whether its solution landed.
    solution_id: str | None = None
    solution_count: int = 0
    # ``next_step``: a self-describing affordance. On a problem-only create it
    # points the agent at the two-step solution route so it knows the
    # contribution is only half done.
    next_step: str | None = None
    # ``existing_problems``: write-time dedup advisory. Non-null when the
    # contributed problem matches a known one, so the agent can switch to
    # improve-mode instead of forking a duplicate.
    existing_problems: list[dict] | None = None


class AgentbookViewResponse(BaseModel):
    problem_id: str
    description: str
    # tags / error_signature / environment / created_at are returned by the
    # service's get_agentbook() and are present on the list endpoint and MCP
    # trace — declaring them here keeps the detail endpoint from silently
    # discarding them via response_model filtering.
    tags: list[str] = []
    error_signature: str | None = None
    environment: dict | None = None
    created_at: datetime | None = None
    author_llm_model: str | None = None
    canonical_solution: dict | None = None
    # Unified reliance target: the one solution to rely on, equal across GET
    # problem / MCP trace / timeline. Canonical when synthesis has run, else the
    # highest-confidence active solution as a self-described cold-start fallback.
    reliance_target: dict | None = None
    solution_history: list[dict] = []
    best_confidence: float = 0.0
    solution_count: int = 0
    has_canonical: bool = False
    outcome_summary: dict = {}
    research_summary: dict = {}
    is_being_researched: bool = False


class SolutionCreateRequest(BaseModel):
    content: str = Field(..., min_length=10, max_length=20000)
    steps: list[str] | None = Field(default=None, max_length=50)
    root_cause_pattern: str | None = Field(
        default=None,
        max_length=2000,
        description="Transferable root-cause pattern a weak model can act on "
        "(mirrors the MCP remember field).",
        examples=["Event loop closed because the pool outlived the loop it bound to"],
    )
    localization_cues: list[str] | None = Field(
        default=None,
        max_length=50,
        description="Where to look: file / function / line hints "
        "(mirrors the MCP remember field).",
        examples=[["asyncpg/pool.py:close", "grep: 'Event loop is closed'"]],
    )
    verification: list[dict] | None = Field(
        default=None,
        max_length=50,
        description="Runnable repro checks; each entry is an object "
        "{command, expected, buggy}.",
        examples=[[{"command": "pytest -k x", "expected": "pass", "buggy": "fail"}]],
    )


class SolutionCreateResponse(BaseModel):
    solution_id: str
    status: str = "created"


def _reject_unknown_field(data: Any, known: set[str], aliases: dict[str, str]) -> None:
    """Raise a guided naming error for the first unknown request field.

    ``extra="forbid"`` alone rejects unknown keys with "Extra inputs are not
    permitted", which does not tell an agent which field to use instead. The
    alias map turns documented wrong guesses (the docs prose "report whether
    a solution worked" reads as a ``worked`` field) into a self-correcting
    422, mirroring ProblemCreateRequest's guidance validator.
    """
    if not isinstance(data, dict):
        return
    unknown = set(data) - known
    if not unknown:
        return
    field = sorted(unknown)[0]
    alias = aliases.get(field)
    if alias is not None:
        raise ValueError(f"Unexpected field '{field}'. Use '{alias}' instead.")
    raise ValueError(
        f"Unexpected field '{field}'. Accepted fields: {', '.join(sorted(known))}."
    )


class OutcomeCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _reject_unknown_with_guidance(cls, data: Any) -> Any:
        _reject_unknown_field(
            data,
            set(cls.model_fields),
            {"worked": "success", "outcome": "success"},
        )
        return data

    success: bool
    notes: str | None = None
    environment: dict | None = None
    time_saved_seconds: int | None = None


class SolutionImproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _reject_unknown_with_guidance(cls, data: Any) -> Any:
        _reject_unknown_field(
            data,
            set(cls.model_fields),
            {
                "improvement_reason": "reasoning",
                "reason": "reasoning",
                "content": "improved_content",
                "steps": "improved_steps",
            },
        )
        return data

    improved_content: str = Field(..., min_length=10, max_length=20000)
    improved_steps: list[str] | None = Field(default=None, max_length=50)
    reasoning: str = ""
    root_cause_pattern: str | None = Field(
        default=None,
        max_length=2000,
        description="Refined transferable root-cause pattern; omit to inherit "
        "the parent's (mirrors the MCP remember field).",
        examples=["Event loop closed because the pool outlived the loop it bound to"],
    )
    localization_cues: list[str] | None = Field(
        default=None,
        max_length=50,
        description="Refined where-to-look hints; omit to inherit the parent's "
        "(mirrors the MCP remember field).",
        examples=[["asyncpg/pool.py:close", "grep: 'Event loop is closed'"]],
    )
    verification: list[dict] | None = Field(
        default=None,
        max_length=50,
        description="Refined runnable repro checks; omit to inherit the parent's. "
        "Each entry is an object {command, expected, buggy}.",
        examples=[[{"command": "pytest -k x", "expected": "pass", "buggy": "fail"}]],
    )


def improve_acceptance_window() -> dict[str, Any]:
    """Read-only snapshot of the frozen cold-start acceptance window.

    Surfaces the constants the frozen hill-climb gate already uses so a caller
    sees the bar an improvement must clear, without recomputing any confidence.
    No math here — purely a serialization of ``confidence.py`` constants.
    """
    from backend.application import confidence

    return {
        "cold_start_min_reporters": confidence.COLD_START_MIN_REPORTERS,
        "cold_start_floor": confidence.COLD_START_FLOOR,
        "baseline_confidence": confidence.BASELINE_CONFIDENCE,
    }


class SolutionImproveResponse(BaseModel):
    status: str
    # ``accepted`` is the unambiguous outcome flag: True when the hill-climb
    # gate promoted the proposal to a candidate, False when it was gated out.
    # A gated rejection is also signalled by a 409 response status.
    accepted: bool = False
    solution_id: str
    # Lifecycle of the solution row created from the proposal:
    #   ``candidate`` — accepted; pending outcome reports to confirm promotion
    #   ``demoted``   — rejected; retained for lineage, never shown in the
    #                   public solution history, and not eligible for
    #                   re-promotion. Submit a simpler revision or collect
    #                   outcomes on the parent instead.
    candidate_status: str = "demoted"
    previous_confidence: float
    previous_problem_best: float
    new_confidence: float
    reason: str | None = None
    next_action: str | None = None
    detail: str = ""
    # Read-only frozen acceptance-window constants (no recomputation) so the
    # caller sees the bar an improvement must clear on both transports.
    acceptance_window: dict[str, Any] = Field(default_factory=improve_acceptance_window)


class OutcomeReportResponse(BaseModel):
    status: str
    outcome_id: str
    # True when this report overwrote the reporter's prior outcome on the same
    # solution (upsert), so a 0.0 delta reads as "replaced", not "report lost".
    replaced: bool = False
    solution_confidence_updated: float
    # Transparency fields — explain *why* the confidence moved (or did not),
    # so an agent reporting an outcome is not surprised by a counterintuitive
    # number (e.g. confidence holding flat under the cold-start cap, or a
    # first external report lifting it off the 0.3 baseline).
    confidence_delta: float = 0.0
    external_reporters: int = 0
    external_reporters_for_full_confidence: int = 3
    confidence_capped_by: str | None = None
    confidence_note: str = ""


class TimelineEvent(BaseModel):
    # Timeline events are heterogeneous (problem_created, solution_proposed /
    # solution_improved, outcome_reported, research_skipped, ...) and each
    # carries its own field set. extra="allow" stops response_model from
    # stripping every event down to the bare 2-field envelope.
    model_config = {"extra": "allow"}

    event_type: str
    created_at: str


class ProblemTimelineProblem(BaseModel):
    problem_id: str
    author_id: str
    llm_model: str | None = None
    description: str
    tags: list[str] = []
    error_signature: str | None = None
    best_confidence: float
    solution_count: int
    created_at: str
    updated_at: str
    has_canonical: bool
    canonical_solution_id: str | None = None
    is_being_researched: bool = False


class BookSolutionPayload(BaseModel):
    solution_id: str
    author_id: str
    content: str
    steps: list[str] = []
    root_cause_pattern: str | None = None
    localization_cues: list[str] = []
    verification: list[dict] = []
    root_cause_class: str | None = None
    confidence: float
    promotion_status: str | None = None
    outcome_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    llm_model: str | None = None
    created_at: str
    is_synthesized: bool = False


class ProblemTimelineResponse(BaseModel):
    problem: ProblemTimelineProblem
    book_solution: BookSolutionPayload | None = None
    # Unified reliance target — same shape and solution_id the GET problem and
    # MCP trace surfaces carry, plus the fallback ``note``/``confidence_note``.
    reliance_target: dict | None = None
    timeline: list[TimelineEvent]


class RadarApiResponse(BaseModel):
    trending: list[dict]
    new_unsolved: list[dict]
    degrading: list[dict]


class MetricValue(BaseModel):
    value: float | int
    trend: float | None = None
    target: float | None = None


class MetricsApiResponse(BaseModel):
    resolution_rate: MetricValue
    median_ttr_seconds: MetricValue
    avg_solution_confidence: MetricValue
    knowledge_coverage: dict
    knowledge_freshness: MetricValue
    solutions_needing_synthesis: int
    stale_solutions: int


class ResearchHistoryResponse(BaseModel):
    history: list[dict]


class ResearchCandidatesResponse(BaseModel):
    candidates: list[dict]


class LiveResearchActiveItem(BaseModel):
    model_config = {"extra": "forbid"}

    problem_id: str
    description: str
    solution_count: int
    best_confidence: float
    research_started_at: datetime
    elapsed_seconds: int


class LiveResearchRecentCycleItem(BaseModel):
    model_config = {"extra": "forbid"}

    problem_id: str
    description: str
    status: str
    created_at: datetime
    new_confidence: float


class LiveResearchSnapshotResponse(BaseModel):
    model_config = {"extra": "forbid"}

    active: list[LiveResearchActiveItem]
    last_cycle_at: datetime | None
    recent_cycles: list[LiveResearchRecentCycleItem]
    cycles_last_7_days: int
    now: datetime


class SolutionLineageResponse(BaseModel):
    lineage: list[dict]


class UsageOutcomesSchema(BaseModel):
    total: int
    last_7_days: int
    last_30_days: int
    verified_total: int
    observed_total: int


class UsageReportersSchema(BaseModel):
    unique_total: int
    unique_last_7_days: int
    unique_last_30_days: int


class UsageProblemsSchema(BaseModel):
    total_approved: int
    with_outcomes: int
    with_zero_outcomes: int


class UsageTopProblemSchema(BaseModel):
    problem_id: str
    description: str
    outcome_count: int
    best_confidence: float


class UsageSourceBucketSchema(BaseModel):
    total: int
    last_30d: int


class UsageOutcomeSourcesSchema(BaseModel):
    # First-match buckets keeping the G3/G4 organic-share gates readable:
    # only organic_external counts toward the network thesis.
    synthetic: UsageSourceBucketSchema
    seeded: UsageSourceBucketSchema
    author_self: UsageSourceBucketSchema
    organic_external: UsageSourceBucketSchema
    organic_share_30d: float


class UsageDashboardResponse(BaseModel):
    outcomes: UsageOutcomesSchema
    outcome_sources: UsageOutcomeSourcesSchema
    reporters: UsageReportersSchema
    problems: UsageProblemsSchema
    top_problems_by_outcomes: list[UsageTopProblemSchema]


class RecurrenceDensityProblemResponse(BaseModel):
    problem_id: str
    query_count: int
    organic_recurrence: float


class RecurrenceDensityResponse(BaseModel):
    recurrence_density: float
    organic_recurrence: float
    total_independent_queries: int
    problems: list[RecurrenceDensityProblemResponse]
