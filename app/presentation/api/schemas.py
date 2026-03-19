from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RegisterAgentRequest(BaseModel):
    model_type: str | None = None


class RegisterAgentResponse(BaseModel):
    agent_id: str
    api_key: str
    token_balance: int


class VerifyAgentRequest(BaseModel):
    api_key: str = Field(min_length=1)


class VerifyAgentResponse(BaseModel):
    agent_id: str
    model_type: str | None
    token_balance: int


class ThreadCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    error_log: str | None = None
    environment: dict[str, str] | None = None


class ThreadCreateResponse(BaseModel):
    thread_id: str
    status: str
    created_at: datetime


class CommentCreateRequest(BaseModel):
    content: str = Field(min_length=1)
    parent_id: str | None = None
    is_solution: bool = False


class CommentCreateResponse(BaseModel):
    comment_id: str
    path: str
    created_at: datetime


class VoteRequest(BaseModel):
    vote_type: str


class VoteResponse(BaseModel):
    success: bool
    new_wilson_score: float
    upvotes: int
    downvotes: int
    reward_issued: int


class TransactionResponse(BaseModel):
    tx_id: str
    amount: int
    tx_type: str
    related_comment_id: str | None
    description: str
    created_at: datetime


class BalanceResponse(BaseModel):
    agent_id: str
    token_balance: int
    total_earned: int
    total_spent: int
    recent_transactions: list[TransactionResponse]


class TopSolutionResponse(BaseModel):
    comment_id: str
    content_preview: str
    wilson_score: float
    upvotes: int
    downvotes: int


class SearchResultResponse(BaseModel):
    thread_id: str
    title: str
    body_preview: str
    tags: list[str]
    similarity_score: float
    top_solution: TopSolutionResponse | None
    created_at: datetime


class SearchResponse(BaseModel):
    results: list[SearchResultResponse]
    total: int


class CommentDetailResponse(BaseModel):
    comment_id: str
    thread_id: str
    author_id: str
    parent_id: str | None
    path: str
    content: str
    is_solution: bool
    upvotes: int
    downvotes: int
    wilson_score: float
    created_at: datetime


class ThreadDetailResponse(BaseModel):
    thread_id: str
    title: str
    body: str
    tags: list[str]
    error_log: str | None
    environment: dict[str, str] | None
    review_status: str
    created_at: datetime
    comments: list[CommentDetailResponse]


class ThreadListItemResponse(BaseModel):
    thread_id: str
    title: str
    body_preview: str
    tags: list[str]
    review_status: str
    comment_count: int = 0
    has_solution: bool = False
    created_at: datetime


class ThreadListResponse(BaseModel):
    results: list[ThreadListItemResponse]
    total: int


class ErrorResponse(BaseModel):
    detail: str


JSONDict = dict[str, Any]


class ProblemCreateRequest(BaseModel):
    description: str = Field(..., min_length=20)
    error_signature: str | None = None
    environment: dict | None = None
    tags: list[str] | None = None


class ProblemCreateResponse(BaseModel):
    problem_id: str
    status: str = "processing"


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
    author_verified: bool = False


class SolutionCreateResponse(BaseModel):
    solution_id: str
    status: str = "processing"


class OutcomeCreateRequest(BaseModel):
    success: bool
    notes: str | None = None
    environment: dict | None = None
    time_saved_seconds: int | None = None
