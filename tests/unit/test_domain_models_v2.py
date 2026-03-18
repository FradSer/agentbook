from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.domain.models import Outcome, Problem, Solution

# ---------------------------------------------------------------------------
# Problem
# ---------------------------------------------------------------------------


def test_problem_requires_author_id_and_description() -> None:
    author = UUID("00000000-0000-0000-0000-000000000001")
    p = Problem(author_id=author, description="Something broke")
    assert p.author_id == author
    assert p.description == "Something broke"


def test_problem_optional_fields_default_to_none() -> None:
    author = UUID("00000000-0000-0000-0000-000000000001")
    p = Problem(author_id=author, description="d")
    assert p.error_signature is None
    assert p.environment is None
    assert p.tags is None
    assert p.embedding is None


def test_problem_id_is_auto_generated_uuid() -> None:
    author = UUID("00000000-0000-0000-0000-000000000001")
    p1 = Problem(author_id=author, description="d")
    p2 = Problem(author_id=author, description="d")
    assert isinstance(p1.problem_id, UUID)
    assert p1.problem_id != p2.problem_id


def test_problem_timestamps_are_utc_now() -> None:
    before = datetime.now(tz=UTC)
    author = UUID("00000000-0000-0000-0000-000000000001")
    p = Problem(author_id=author, description="d")
    after = datetime.now(tz=UTC)
    assert before <= p.created_at <= after
    assert before <= p.last_activity_at <= after


def test_problem_best_confidence_defaults_to_zero() -> None:
    author = UUID("00000000-0000-0000-0000-000000000001")
    p = Problem(author_id=author, description="d")
    assert p.best_confidence == 0.0


def test_problem_solution_count_defaults_to_zero() -> None:
    author = UUID("00000000-0000-0000-0000-000000000001")
    p = Problem(author_id=author, description="d")
    assert p.solution_count == 0


# ---------------------------------------------------------------------------
# Solution
# ---------------------------------------------------------------------------


def test_solution_requires_problem_id_author_id_content() -> None:
    pid = UUID("00000000-0000-0000-0000-000000000002")
    aid = UUID("00000000-0000-0000-0000-000000000003")
    s = Solution(problem_id=pid, author_id=aid, content="Try this")
    assert s.problem_id == pid
    assert s.author_id == aid
    assert s.content == "Try this"


def test_solution_steps_defaults_to_empty_list() -> None:
    pid = UUID("00000000-0000-0000-0000-000000000002")
    aid = UUID("00000000-0000-0000-0000-000000000003")
    s = Solution(problem_id=pid, author_id=aid, content="c")
    assert s.steps == []


def test_solution_author_verified_defaults_to_false() -> None:
    pid = UUID("00000000-0000-0000-0000-000000000002")
    aid = UUID("00000000-0000-0000-0000-000000000003")
    s = Solution(problem_id=pid, author_id=aid, content="c")
    assert s.author_verified is False


def test_solution_confidence_is_0_3_when_author_not_verified() -> None:
    pid = UUID("00000000-0000-0000-0000-000000000002")
    aid = UUID("00000000-0000-0000-0000-000000000003")
    s = Solution(problem_id=pid, author_id=aid, content="c")
    assert s.confidence == pytest.approx(0.3)


def test_solution_confidence_is_0_5_when_author_verified() -> None:
    pid = UUID("00000000-0000-0000-0000-000000000002")
    aid = UUID("00000000-0000-0000-0000-000000000003")
    s = Solution(problem_id=pid, author_id=aid, content="c", author_verified=True)
    assert s.confidence == pytest.approx(0.5)


def test_solution_counts_default_to_zero() -> None:
    pid = UUID("00000000-0000-0000-0000-000000000002")
    aid = UUID("00000000-0000-0000-0000-000000000003")
    s = Solution(problem_id=pid, author_id=aid, content="c")
    assert s.outcome_count == 0
    assert s.success_count == 0
    assert s.failure_count == 0


def test_solution_environment_scores_defaults_to_empty_dict() -> None:
    pid = UUID("00000000-0000-0000-0000-000000000002")
    aid = UUID("00000000-0000-0000-0000-000000000003")
    s = Solution(problem_id=pid, author_id=aid, content="c")
    assert s.environment_scores == {}


def test_solution_canonical_id_defaults_to_none() -> None:
    pid = UUID("00000000-0000-0000-0000-000000000002")
    aid = UUID("00000000-0000-0000-0000-000000000003")
    s = Solution(problem_id=pid, author_id=aid, content="c")
    assert s.canonical_id is None


def test_solution_id_is_auto_generated_uuid() -> None:
    pid = UUID("00000000-0000-0000-0000-000000000002")
    aid = UUID("00000000-0000-0000-0000-000000000003")
    s1 = Solution(problem_id=pid, author_id=aid, content="c")
    s2 = Solution(problem_id=pid, author_id=aid, content="c")
    assert isinstance(s1.solution_id, UUID)
    assert s1.solution_id != s2.solution_id


def test_solution_timestamps_are_utc_now() -> None:
    before = datetime.now(tz=UTC)
    pid = UUID("00000000-0000-0000-0000-000000000002")
    aid = UUID("00000000-0000-0000-0000-000000000003")
    s = Solution(problem_id=pid, author_id=aid, content="c")
    after = datetime.now(tz=UTC)
    assert before <= s.created_at <= after
    assert before <= s.updated_at <= after


# ---------------------------------------------------------------------------
# Outcome
# ---------------------------------------------------------------------------


def test_outcome_requires_solution_id_reporter_id_success() -> None:
    sid = UUID("00000000-0000-0000-0000-000000000004")
    rid = UUID("00000000-0000-0000-0000-000000000005")
    o = Outcome(solution_id=sid, reporter_id=rid, success=True)
    assert o.solution_id == sid
    assert o.reporter_id == rid
    assert o.success is True


def test_outcome_optional_fields_default_to_none() -> None:
    sid = UUID("00000000-0000-0000-0000-000000000004")
    rid = UUID("00000000-0000-0000-0000-000000000005")
    o = Outcome(solution_id=sid, reporter_id=rid, success=False)
    assert o.environment is None
    assert o.error_after is None
    assert o.time_saved_seconds is None
    assert o.notes is None


def test_outcome_weight_defaults_to_1_0() -> None:
    sid = UUID("00000000-0000-0000-0000-000000000004")
    rid = UUID("00000000-0000-0000-0000-000000000005")
    o = Outcome(solution_id=sid, reporter_id=rid, success=True)
    assert o.weight == pytest.approx(1.0)


def test_outcome_id_is_auto_generated_uuid() -> None:
    sid = UUID("00000000-0000-0000-0000-000000000004")
    rid = UUID("00000000-0000-0000-0000-000000000005")
    o1 = Outcome(solution_id=sid, reporter_id=rid, success=True)
    o2 = Outcome(solution_id=sid, reporter_id=rid, success=True)
    assert isinstance(o1.outcome_id, UUID)
    assert o1.outcome_id != o2.outcome_id


def test_outcome_created_at_is_utc_now() -> None:
    before = datetime.now(tz=UTC)
    sid = UUID("00000000-0000-0000-0000-000000000004")
    rid = UUID("00000000-0000-0000-0000-000000000005")
    o = Outcome(solution_id=sid, reporter_id=rid, success=True)
    after = datetime.now(tz=UTC)
    assert before <= o.created_at <= after
