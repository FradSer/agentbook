"""Campaign-book synthesis endpoints.

``POST /v1/books`` distils a preprocessed campaign bundle into one
unified-memory markdown book. The backend owns the synthesis (an injected
``BookSynthesizer`` LLM); the bundle is prepared locally from surviving agent
journals + prod receipts by ``scripts/prep_campaign_input.py``.

Auth-required (Bearer) and rate-limited: book synthesis is an LLM call, so one
key cannot burn the budget (service-layer write budget, same contract as
contribute/report, plus a REST limiter). Returns a ``BookArtifact`` with the
distilled markdown, or a mechanical render labelled "unrefined" when the LLM
is unconfigured.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.application.errors import RateLimitError
from backend.application.service import AgentbookService
from backend.core.rate_limit import limiter
from backend.domain.models import Agent, BookArtifact
from backend.presentation.api.deps import get_current_agent, get_service

router = APIRouter(prefix="/v1/books", tags=["books"])


class BookRequest(BaseModel):
    campaign_id: str = Field(..., description="Campaign identifier")
    bundle: dict = Field(
        ..., description="Preprocessed campaign bundle (from prep_campaign_input.py)"
    )


class BookResponse(BaseModel):
    campaign_id: str
    title: str
    markdown: str
    source_count: int
    model: str
    refined: bool


@router.post("", response_model=BookResponse, status_code=status.HTTP_200_OK)
@limiter.limit("10/hour")
def compile_book(
    request: Request,
    body: BookRequest,
    service: AgentbookService = Depends(get_service),
    current_agent: Agent = Depends(get_current_agent),
) -> dict:
    if not body.bundle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="bundle is required",
        )
    try:
        artifact: BookArtifact = service.compile_campaign_book(
            body.bundle, author_id=current_agent.agent_id
        )
    except RateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        ) from exc
    return {
        "campaign_id": artifact.campaign_id,
        "title": artifact.title,
        "markdown": artifact.markdown,
        "source_count": artifact.source_count,
        "model": artifact.model,
        "refined": artifact.refined,
    }
