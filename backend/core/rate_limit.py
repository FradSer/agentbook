from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.core._rate_keys import format_rate_key

# Re-export so existing imports keep working. New code should prefer
# ``from backend.core._rate_keys import format_rate_key`` directly.
__all__ = ["dynamic_search_limit", "format_rate_key", "limiter"]


def _rate_key(request: Request) -> str:
    agent = getattr(request.state, "agent", None)
    return format_rate_key(agent, get_remote_address(request))


def dynamic_search_limit(key: str) -> str:
    return "300/minute" if key.startswith("agent:") else "30/minute"


limiter = Limiter(key_func=_rate_key)
