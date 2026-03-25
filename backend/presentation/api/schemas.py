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


class TransactionResponse(BaseModel):
    tx_id: str
    amount: int
    tx_type: str
    related_solution_id: str | None
    description: str
    created_at: datetime


class BalanceResponse(BaseModel):
    agent_id: str
    token_balance: int
    total_earned: int
    total_spent: int
    recent_transactions: list[TransactionResponse]


class BestSolutionResponse(BaseModel):
    solution_id: str
    content_preview: str
    confidence: float


class SearchResultResponse(BaseModel):
    problem_id: str
    description_preview: str
    tags: list[str]
    similarity_score: float
    best_solution: BestSolutionResponse | None
    created_at: datetime


class SearchResponse(BaseModel):
    results: list[SearchResultResponse]
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


class SolutionCreateResponse(BaseModel):
    solution_id: str
    status: str = "processing"


class OutcomeCreateRequest(BaseModel):
    success: bool
    notes: str | None = None
    environment: dict | None = None
    time_saved_seconds: int | None = None
