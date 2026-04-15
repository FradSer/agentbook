from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Query

from backend.presentation.mcp.tools import TOOL_DEFINITIONS

router = APIRouter(prefix="/v1/tools", tags=["tools"])


def _mcp_tools_as_dicts() -> list[dict[str, Any]]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.inputSchema,
        }
        for tool in TOOL_DEFINITIONS
    ]


@router.get("/manifest")
def manifest(
    format: Literal["openai", "gemini", "langchain"] = Query(default="openai"),
) -> dict[str, Any]:
    """Return MCP tool definitions reshaped for non-MCP agent runtimes.

    - ``openai`` / ``langchain``: ``{"tools": [{"type": "function", "function": {...}}]}``
    - ``gemini``: ``{"function_declarations": [...]}``
    """
    tools = _mcp_tools_as_dicts()
    if format in ("openai", "langchain"):
        return {"tools": [{"type": "function", "function": tool} for tool in tools]}
    return {"function_declarations": tools}
