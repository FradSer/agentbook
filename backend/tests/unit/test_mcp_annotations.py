"""Regression coverage for MCP tool annotation metadata."""

from __future__ import annotations

from backend.presentation.mcp.tools import TOOL_DEFINITIONS

_EXPECTED_ANNOTATIONS = {
    "recall": {
        "readOnlyHint": True,
        "destructiveHint": False,
        "openWorldHint": True,
    },
    "remember": {
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": True,
    },
    "report": {
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": False,
    },
    "trace": {
        "readOnlyHint": True,
        "destructiveHint": False,
        "openWorldHint": False,
    },
    "verify": {
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": False,
    },
    "compile_book": {
        "readOnlyHint": True,
        "destructiveHint": False,
        "openWorldHint": True,
    },
}


def test_mcp_tools_declare_connector_annotations() -> None:
    tools = {tool.name: tool for tool in TOOL_DEFINITIONS}

    assert set(tools) == set(_EXPECTED_ANNOTATIONS)
    for name, expected in _EXPECTED_ANNOTATIONS.items():
        annotations = tools[name].annotations
        assert annotations is not None, f"{name} has no annotations"
        actual = annotations.model_dump(exclude_none=True)
        assert {key: actual.get(key) for key in expected} == expected
