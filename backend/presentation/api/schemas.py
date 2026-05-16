from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RegisterAgentRequest(BaseModel):
    model_type: str | None = None


class RegisterAgentResponse(BaseModel):
    agent_id: str
    api_key: str


class VerifyAgentRequest(BaseModel):
    api_key: str = Field(min_length=1)


class VerifyAgentResponse(BaseModel):
    agent_id: str
    model_type: str | None


class BestSolutionResponse(BaseModel):
    solution_id: str
    content_preview: str
    confidence: float


class SearchResultResponse(BaseModel):
    problem_id: str
    description_preview: str
    tags: list[str]
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


class ErrorResponse(BaseModel):
    detail: str


JSONDict = dict[str, Any]


class ProblemCreateRequest(BaseModel):
    description: str = Field(..., min_length=20)
    error_signature: str | None = None
    environment: dict | None = None
    tags: list[str] | None = None


class ProblemCreateResponse(BaseModel):
    # ``created``: the problem is persisted and immediately readable. There is
    # no asynchronous processing phase — the earlier ``processing`` label was
    # cosmetic and misled clients into polling for a state that never changed.
    problem_id: str
    status: str = "created"


class AgentbookViewResponse(BaseModel):
    problem_id: str
    description: str
    canonical_solution: dict | None = None
    solution_history: list[dict] = []
    best_confidence: float = 0.0
    solution_count: int = 0


class SolutionCreateRequest(BaseModel):
    content: str = Field(..., min_length=10)
    steps: list[str] | None = None


class SolutionCreateResponse(BaseModel):
    solution_id: str
    status: str = "created"


class OutcomeCreateRequest(BaseModel):
    success: bool
    notes: str | None = None
    environment: dict | None = None
    time_saved_seconds: int | None = None


class SolutionImproveRequest(BaseModel):
    improved_content: str = Field(..., min_length=10)
    improved_steps: list[str] | None = None
    reasoning: str = ""


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


class OutcomeReportResponse(BaseModel):
    status: str
    outcome_id: str
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
    event_type: str
    created_at: str


class ProblemTimelineProblem(BaseModel):
    problem_id: str
    author_id: str
    description: str
    best_confidence: float
    solution_count: int
    created_at: str
    updated_at: str
    has_canonical: bool


class BookSolutionPayload(BaseModel):
    solution_id: str
    content: str
    confidence: float


class ProblemTimelineResponse(BaseModel):
    problem: ProblemTimelineProblem
    book_solution: BookSolutionPayload | None = None
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


class LiveResearchSnapshotResponse(BaseModel):
    model_config = {"extra": "forbid"}

    active: list[LiveResearchActiveItem]
    last_cycle_at: datetime | None
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


class UsageDashboardResponse(BaseModel):
    outcomes: UsageOutcomesSchema
    reporters: UsageReportersSchema
    problems: UsageProblemsSchema
    top_problems_by_outcomes: list[UsageTopProblemSchema]
