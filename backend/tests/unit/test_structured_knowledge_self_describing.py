"""Structured-knowledge write fields self-describe in the REST contract.

Covers backend/tests/features/structured-knowledge-self-describing.feature.

The differentiating asset (root_cause_pattern, localization_cues, verification)
is described inline by the MCP ``remember`` inputSchema. The REST write models
must carry the same per-field descriptions so an agent reading ``/openapi.json``
constructs a valid contribution without trial-and-error 422s.
"""

from __future__ import annotations

import pytest

from backend.presentation.api.schemas import (
    ProblemCreateRequest,
    SolutionCreateRequest,
)

_STRUCTURED_FIELDS = ["root_cause_pattern", "localization_cues", "verification"]


@pytest.mark.parametrize("model", [SolutionCreateRequest, ProblemCreateRequest])
@pytest.mark.parametrize("field", _STRUCTURED_FIELDS)
def test_structured_field_carries_description(model, field):
    schema = model.model_json_schema()
    prop = schema["properties"][field]
    description = prop.get("description", "")
    assert description.strip(), (
        f"{model.__name__}.{field} must carry a non-empty description so a REST "
        f"agent reading /openapi.json knows its shape without a trial 422"
    )


@pytest.mark.parametrize("model", [SolutionCreateRequest, ProblemCreateRequest])
def test_localization_cues_advertises_an_example(model):
    schema = model.model_json_schema()
    prop = schema["properties"]["localization_cues"]
    # Pydantic surfaces Field(examples=...) as either `examples` (list) on the
    # property or inside the schema; assert at least one concrete example shape.
    examples = prop.get("examples")
    assert examples, (
        f"{model.__name__}.localization_cues must advertise an example so the "
        f"agent can construct a valid where-to-look array on the first attempt"
    )
