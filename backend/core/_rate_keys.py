"""Rate-limit bucket key formatter shared by REST and MCP surfaces.

Lives in a neutral module because both ``backend/core/rate_limit.py``
(slowapi-coupled, REST) and ``backend/core/mcp_rate_limit.py``
(in-process sliding window) need to produce identical keys for a
caller — but neither should depend on the other. The leading
underscore signals "internal helper, not a public API".

The two surfaces share keying but NOT bucket state — REST and MCP
limiters are separate processes/structures. A caller hitting REST + MCP
sees one key on each side, two independent quotas. That's intentional:
keying ensures we can correlate; the budget split is per-surface.
"""

from __future__ import annotations

from backend.domain.models import Agent


def format_rate_key(agent: Agent | None, remote_addr: str | None) -> str:
    """Canonical rate-limit bucket key.

    Authenticated callers key by ``agent_id`` so the per-agent quota is
    independent of any anonymous traffic from the same IP. Anonymous
    callers fall back to remote address (``"unknown"`` when missing).
    """
    if agent is not None:
        return f"agent:{agent.agent_id}"
    return f"ip:{remote_addr or 'unknown'}"
