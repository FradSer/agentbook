"""MCP (Model Context Protocol) presentation layer.

This module provides SSE-based MCP endpoints for agent runtime integration.
Follows Clean Architecture: all business logic is delegated to AgentbookService.
"""

from __future__ import annotations

__all__ = ["sse_router"]

from app.presentation.mcp.sse import sse_router
