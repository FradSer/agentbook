"""Unit tests for MCP tool definitions (structural regression guards)."""

from __future__ import annotations

from backend.presentation.mcp.tools import _TOOL_DEFINITIONS

_TOOL_NAMES = [t.name for t in _TOOL_DEFINITIONS]


def test_mcp_has_four_tools():
    assert len(_TOOL_NAMES) == 4, (
        f"Expected 4 tools, got {len(_TOOL_NAMES)}: {_TOOL_NAMES}"
    )


def test_mcp_tools_include_required_names():
    expected = {"search", "contribute", "report", "inspect"}
    for name in expected:
        assert name in _TOOL_NAMES, f"Missing tool: {name}"


def test_mcp_old_tools_removed():
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
        assert name not in _TOOL_NAMES, f"Old tool still present: {name}"
