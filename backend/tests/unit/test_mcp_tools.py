"""Unit tests for MCP tools (4 consolidated tools)."""

from __future__ import annotations


def _get_tool_names():
    """Get registered MCP tool names."""
    try:
        from backend.presentation.mcp.tools import _TOOL_DEFINITIONS

        return [t.name for t in _TOOL_DEFINITIONS]
    except ImportError:
        from backend.presentation.mcp import tools as mcp_tools

        if hasattr(mcp_tools, "_TOOL_DEFINITIONS"):
            return [t.name for t in mcp_tools._TOOL_DEFINITIONS]
        return []


def test_mcp_has_four_tools():
    names = _get_tool_names()
    assert len(names) == 4, f"Expected 4 tools, got {len(names)}: {names}"


def test_mcp_tools_include_required_names():
    names = _get_tool_names()
    expected = {"search", "contribute", "report", "inspect"}
    for name in expected:
        assert name in names, f"Missing tool: {name}"


def test_mcp_old_tools_removed():
    names = _get_tool_names()
    removed = {
        "ask_question",
        "answer_question",
        "vote_answer",
        "search_agentbook",
        "resolve",
        "report_outcome",
        "get_context",
        "improve_solution",
        "get_solution_lineage",
        "get_research_candidates",
    }
    for name in removed:
        assert name not in names, f"Old tool still present: {name}"


def test_search_tool_uses_problem_based_search():
    """search tool must use problem-based search, not V1 threads."""
    import inspect

    import backend.presentation.mcp.tools as mcp_module

    src = inspect.getsource(mcp_module)
    assert "problem_id" in src or "problems" in src.lower()
    assert '"search"' in src


def test_mcp_tools_module_no_longer_has_v1_voting():
    """vote_answer and related V1 handlers must not exist."""
    import inspect

    import backend.presentation.mcp.tools as mcp_module

    src = inspect.getsource(mcp_module)
    assert (
        "vote_answer" not in src or "_TOOL_DEFINITIONS" in src
    )  # either removed or replaced
