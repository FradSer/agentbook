"""Per-request agent context for MCP Streamable HTTP transport.

Uses contextvars so each async request task carries its own agent identity
and remote address without mutating shared server state.
"""

from __future__ import annotations

from contextvars import ContextVar

from backend.domain.models import Agent

current_agent: ContextVar[Agent | None] = ContextVar("mcp_current_agent", default=None)
current_remote_addr: ContextVar[str | None] = ContextVar(
    "mcp_current_remote_addr", default=None
)
