from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _rate_key(request: Request) -> str:
    agent = getattr(request.state, "agent", None)
    if agent is not None:
        return f"agent:{agent.agent_id}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_rate_key)
