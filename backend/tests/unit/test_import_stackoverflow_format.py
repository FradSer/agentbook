"""Unit tests for Stack Overflow import formatting helpers."""

from backend.scripts.import_stackoverflow import (
    _extract_steps,
    build_problem_description,
    so_error_signature,
)


def test_so_error_signature_stable():
    assert so_error_signature(231767) == "so:q:231767"


def test_build_problem_description_includes_attribution():
    q = {
        "question_id": 42,
        "title": "How to test?",
        "body": "<p>Body text here for the question.</p>",
    }
    desc = build_problem_description(q)
    assert "How to test?" in desc
    assert "stackoverflow.com/questions/42" in desc
    assert "CC BY-SA" in desc


def test_extract_steps_from_numbered_list():
    md = "1. First do this thing\n2. Then do that other thing\n3. Finally verify"
    steps = _extract_steps(md)
    assert len(steps) >= 2
    assert "First" in steps[0]
