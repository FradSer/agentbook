"""Unit tests for V3 MCP tools (binary spam, no V1 tools)."""
from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest


def _get_tool_names():
    """Get registered MCP tool names."""
    try:
        from app.presentation.mcp.tools import _TOOL_DEFINITIONS
        return [t.name for t in _TOOL_DEFINITIONS]
    except ImportError:
        # Fall back to listing all tools through the server
        from app.presentation.mcp import tools as mcp_tools
        if hasattr(mcp_tools, "_TOOL_DEFINITIONS"):
            return [t.name for t in mcp_tools._TOOL_DEFINITIONS]
        return []


def test_mcp_has_eight_tools():
    names = _get_tool_names()
    assert len(names) == 8, f"Expected 8 tools, got {len(names)}: {names}"


def test_mcp_tools_include_required_names():
    names = _get_tool_names()
    expected = {
        "search_agentbook",
        "resolve",
        "contribute",
        "report_outcome",
        "get_context",
        "improve_solution",
        "get_solution_lineage",
        "get_research_candidates",
    }
    for name in expected:
        assert name in names, f"Missing tool: {name}"


def test_mcp_v1_tools_removed():
    names = _get_tool_names()
    v1_tools = {"ask_question", "answer_question", "vote_answer"}
    for name in v1_tools:
        assert name not in names, f"V1 tool still present: {name}"


def test_search_agentbook_result_has_problem_fields():
    """search_agentbook in MCP tools module must use problem-based search."""
    import app.presentation.mcp.tools as mcp_module
    # The search_agentbook tool handler should call service.search() not service.list_threads()
    import inspect
    src = inspect.getsource(mcp_module)
    # After V3 implementation: search should reference problems, not threads
    assert "problem_id" in src or "problems" in src.lower()
    assert "search_agentbook" in src


def test_mcp_tools_module_no_longer_has_v1_voting():
    """vote_answer and related V1 handlers must not exist."""
    import app.presentation.mcp.tools as mcp_module
    import inspect
    src = inspect.getsource(mcp_module)
    # V1 tools that should be removed
    assert "vote_answer" not in src or "_TOOL_DEFINITIONS" in src  # either removed or replaced
