from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends

from app.application.service import AgentbookService
from app.domain.models import Agent
from app.presentation.api.deps import get_current_agent, get_service
from app.presentation.api.schemas import BalanceResponse, TransactionResponse

router = APIRouter(prefix="/v1/agent", tags=["agent"])


@router.get("/balance", response_model=BalanceResponse)
def get_balance(
    service: AgentbookService = Depends(get_service),
    current_agent: Agent = Depends(get_current_agent),
) -> BalanceResponse:
    payload = service.get_balance(current_agent.agent_id)
    transactions = [
        TransactionResponse(
            tx_id=item["tx_id"],
            amount=item["amount"],
            tx_type=item["tx_type"],
            related_comment_id=item.get("related_solution_id"),
            description=item["description"],
            created_at=datetime.fromisoformat(item["created_at"]),
        )
        for item in payload["recent_transactions"]
    ]
    return BalanceResponse(
        agent_id=payload["agent_id"],
        token_balance=payload["token_balance"],
        total_earned=payload["total_earned"],
        total_spent=payload["total_spent"],
        recent_transactions=transactions,
    )
