from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.domain.models import Agent


def format_rate_key(agent: Agent | None, remote_addr: str | None) -> str:
    """Canonical rate-limit bucket key shared by REST and MCP surfaces.

    Authenticated callers key by ``agent_id`` so the per-agent quota is
    independent of any anonymous traffic from the same IP. Anonymous callers
    fall back to remote address (``"unknown"`` when missing). MCP imports
    this helper directly so the two surfaces stay in lock-step on tier
    selection — the underlying limiter implementations differ (slowapi for
    REST, an in-process sliding window for MCP, see
    ``backend/core/mcp_rate_limit.py``) but the keying must not.
    """
    if agent is not None:
        return f"agent:{agent.agent_id}"
    return f"ip:{remote_addr or 'unknown'}"


def _rate_key(request: Request) -> str:
    agent = getattr(request.state, "agent", None)
    return format_rate_key(agent, get_remote_address(request))


def dynamic_search_limit(key: str) -> str:
    return "300/minute" if key.startswith("agent:") else "30/minute"


limiter = Limiter(key_func=_rate_key)
