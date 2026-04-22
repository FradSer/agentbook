"""Unit tests for domain models (Problem, Solution, Outcome)."""

from __future__ import annotations

import importlib
from datetime import UTC, datetime
from uuid import UUID

import pytest

from backend.domain.models import Outcome, Problem, Solution

AUTHOR_ID = UUID("00000000-0000-0000-0000-000000000001")
PROBLEM_ID = UUID("00000000-0000-0000-0000-000000000002")
SOLUTION_ID = UUID("00000000-0000-0000-0000-000000000004")
REPORTER_ID = UUID("00000000-0000-0000-0000-000000000005")


def _make_problem(**overrides: object) -> Problem:
    return Problem(author_id=AUTHOR_ID, description="Something broke", **overrides)


def _make_solution(**overrides: object) -> Solution:
    return Solution(
        problem_id=PROBLEM_ID,
        author_id=AUTHOR_ID,
        content="Try this",
        **overrides,
    )


def _make_outcome(**overrides: object) -> Outcome:
    success = overrides.pop("success", True)
    return Outcome(
        solution_id=SOLUTION_ID,
        reporter_id=REPORTER_ID,
        success=bool(success),
        **overrides,
    )


def test_given_problem_inputs_when_constructing_then_required_fields_are_preserved() -> None:
    problem = _make_problem()
    assert problem.author_id == AUTHOR_ID
    assert problem.description == "Something broke"


@pytest.mark.parametrize(
    ("field_name", "expected"),
    [
        ("error_signature", None),
        ("environment", None),
        ("tags", None),
        ("embedding", None),
        ("best_confidence", 0.0),
        ("solution_count", 0),
        ("review_status", None),
        ("review_score", None),
        ("reviewed_at", None),
        ("canonical_solution_id", None),
        ("version", 1),
    ],
)
def test_given_problem_defaults_when_constructing_then_fields_match_contract(
    field_name: str, expected: object
) -> None:
    problem = _make_problem()
    assert getattr(problem, field_name) == expected
    assert problem.last_activity_at is not None


def test_given_new_problems_when_constructing_then_problem_ids_are_unique_uuids() -> None:
    first = _make_problem()
    second = _make_problem()
    assert isinstance(first.problem_id, UUID)
    assert first.problem_id != second.problem_id


def test_given_new_problem_when_constructing_then_problem_timestamps_are_utc_now() -> None:
    before = datetime.now(tz=UTC)
    problem = _make_problem()
    after = datetime.now(tz=UTC)
    assert before <= problem.created_at <= after
    assert before <= problem.last_activity_at <= after


def test_given_solution_inputs_when_constructing_then_required_fields_are_preserved() -> None:
    solution = _make_solution()
    assert solution.problem_id == PROBLEM_ID
    assert solution.author_id == AUTHOR_ID
    assert solution.content == "Try this"


@pytest.mark.parametrize(
    ("field_name", "expected"),
    [
        ("steps", []),
        ("confidence", pytest.approx(0.3)),
        ("outcome_count", 0),
        ("success_count", 0),
        ("failure_count", 0),
        ("environment_scores", {}),
        ("canonical_id", None),
        ("review_status", None),
        ("review_score", None),
        ("reviewed_at", None),
        ("parent_solution_id", None),
    ],
)
def test_given_solution_defaults_when_constructing_then_fields_match_contract(
    field_name: str, expected: object
) -> None:
    solution = _make_solution()
    assert getattr(solution, field_name) == expected


def test_given_new_solutions_when_constructing_then_solution_ids_are_unique_uuids() -> None:
    first = _make_solution()
    second = _make_solution()
    assert isinstance(first.solution_id, UUID)
    assert first.solution_id != second.solution_id


def test_given_new_solution_when_constructing_then_solution_timestamps_are_utc_now() -> None:
    before = datetime.now(tz=UTC)
    solution = _make_solution()
    after = datetime.now(tz=UTC)
    assert before <= solution.created_at <= after
    assert before <= solution.updated_at <= after


def test_given_outcome_inputs_when_constructing_then_required_fields_are_preserved() -> None:
    outcome = _make_outcome()
    assert outcome.solution_id == SOLUTION_ID
    assert outcome.reporter_id == REPORTER_ID
    assert outcome.success is True


@pytest.mark.parametrize(
    ("field_name", "expected"),
    [
        ("environment", None),
        ("error_after", None),
        ("time_saved_seconds", None),
        ("notes", None),
        ("weight", pytest.approx(1.0)),
    ],
)
def test_given_outcome_defaults_when_constructing_then_fields_match_contract(
    field_name: str, expected: object
) -> None:
    outcome = _make_outcome(success=False)
    assert getattr(outcome, field_name) == expected


def test_given_new_outcomes_when_constructing_then_outcome_ids_are_unique_uuids() -> None:
    first = _make_outcome()
    second = _make_outcome()
    assert isinstance(first.outcome_id, UUID)
    assert first.outcome_id != second.outcome_id


def test_given_new_outcome_when_constructing_then_created_at_is_utc_now() -> None:
    before = datetime.now(tz=UTC)
    outcome = _make_outcome()
    after = datetime.now(tz=UTC)
    assert before <= outcome.created_at <= after


@pytest.mark.parametrize("deprecated_symbol", ["Thread", "Comment", "Vote"])
def test_given_removed_domain_symbol_when_importing_then_import_error_is_raised(
    deprecated_symbol: str,
) -> None:
    with pytest.raises(ImportError):
        exec(f"from backend.domain.models import {deprecated_symbol}")  # noqa: S102


def test_given_removed_scoring_module_when_importing_then_module_not_found_is_raised() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("backend.domain.scoring")


@pytest.mark.parametrize(
    ("module_path", "removed_symbol"),
    [
        ("backend.application.errors", "DuplicateVoteError"),
        ("backend.domain.models", "TokenTransaction"),
    ],
)
def test_given_removed_symbol_when_reading_module_then_symbol_is_absent(
    module_path: str, removed_symbol: str
) -> None:
    module = importlib.import_module(module_path)
    assert not hasattr(module, removed_symbol)


@pytest.mark.parametrize(
    ("repo_name", "required_method"),
    [
        ("ProblemRepository", "delete"),
        ("ProblemRepository", "find_unreviewed"),
        ("SolutionRepository", "delete"),
        ("SolutionRepository", "find_unreviewed"),
        ("SolutionRepository", "list_by_problem_ranked"),
    ],
)
def test_given_repository_protocol_when_inspecting_then_required_method_exists(
    repo_name: str, required_method: str
) -> None:
    from backend.domain import repositories as repos

    repo_type = getattr(repos, repo_name)
    assert hasattr(repo_type, required_method)


@pytest.mark.parametrize(
    "removed_repo_name",
    ["ThreadRepository", "CommentRepository", "VoteRepository"],
)
def test_given_removed_repository_protocol_when_inspecting_then_symbol_is_absent(
    removed_repo_name: str,
) -> None:
    from backend.domain import repositories as repos

    assert not hasattr(repos, removed_repo_name)
