"""Unit tests for MCP tool definitions (structural regression guards)."""

from __future__ import annotations

from backend.presentation.mcp.tools import TOOL_DEFINITIONS

_TOOL_NAMES = [t.name for t in TOOL_DEFINITIONS]


def test_mcp_has_eight_tools_after_aliasing():
    # Four legacy (search/contribute/report/inspect) + four memory-shaped
    # (recall/remember/trace/verify). Legacy names remain for 6 months
    # with deprecation metadata.
    assert len(_TOOL_NAMES) == 8, (
        f"Expected 8 tools, got {len(_TOOL_NAMES)}: {_TOOL_NAMES}"
    )


def test_mcp_tools_include_required_names():
    expected = {
        "search",
        "contribute",
        "report",
        "inspect",
        "recall",
        "remember",
        "trace",
        "verify",
    }
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
