"""Unit tests for MCP tool definitions (structural regression guards)."""

from __future__ import annotations

import pytest

from backend.presentation.mcp.tools import TOOL_DEFINITIONS

_TOOL_NAMES = [t.name for t in TOOL_DEFINITIONS]


def test_mcp_exposes_six_memory_tools():
    assert len(_TOOL_NAMES) == 6, (
        f"Expected 6 tools, got {len(_TOOL_NAMES)}: {_TOOL_NAMES}"
    )


@pytest.mark.parametrize(
    "required_name",
    [
        "recall",
        "remember",
        "report",
        "trace",
        "verify",
    ],
)
def test_given_current_manifest_when_listing_tools_then_required_name_exists(
    required_name: str,
):
    assert required_name in _TOOL_NAMES, f"Missing tool: {required_name}"


@pytest.mark.parametrize(
    "removed_name",
    [
        "search",
        "contribute",
        "inspect",
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
    ],
)
def test_given_current_manifest_when_listing_tools_then_removed_name_is_absent(
    removed_name: str,
):
    assert removed_name not in _TOOL_NAMES, f"Old tool still present: {removed_name}"
