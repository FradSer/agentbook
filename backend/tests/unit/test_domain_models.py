"""Unit tests for domain models (Problem, Solution, Outcome)."""

from __future__ import annotations

import importlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from backend.domain.models import Outcome, Problem, Solution

# Problem — construction & defaults


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
    p = Problem(author_id=uuid4(), description="d")
    assert p.best_confidence == 0.0


def test_problem_solution_count_defaults_to_zero() -> None:
    p = Problem(author_id=uuid4(), description="d")
    assert p.solution_count == 0


def test_problem_has_review_fields():
    p = Problem(author_id=uuid4(), description="Docker Alpine numpy error")
    assert p.review_status is None
    assert p.review_score is None
    assert p.reviewed_at is None


def test_problem_has_canonical_solution_id():
    p = Problem(author_id=uuid4(), description="Some error")
    assert p.canonical_solution_id is None


def test_problem_has_required_tracking_fields():
    p = Problem(author_id=uuid4(), description="Some error")
    assert p.version == 1
    assert p.last_activity_at is not None


# Solution — construction & defaults


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


def test_solution_confidence_defaults_to_0_3() -> None:
    pid = UUID("00000000-0000-0000-0000-000000000002")
    aid = UUID("00000000-0000-0000-0000-000000000003")
    s = Solution(problem_id=pid, author_id=aid, content="c")
    assert s.confidence == pytest.approx(0.3)


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


def test_solution_has_review_fields():
    s = Solution(problem_id=uuid4(), author_id=uuid4(), content="Fix it")
    assert s.review_status is None
    assert s.review_score is None
    assert s.reviewed_at is None


def test_solution_has_parent_solution_id():
    s = Solution(problem_id=uuid4(), author_id=uuid4(), content="Fix it")
    assert s.parent_solution_id is None


# Outcome — construction & defaults


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


# Structural guards — deprecated types must not exist


def test_thread_not_importable():
    with pytest.raises(ImportError):
        from backend.domain.models import Thread  # noqa: F401


def test_comment_not_importable():
    with pytest.raises(ImportError):
        from backend.domain.models import Comment  # noqa: F401


def test_vote_not_importable():
    with pytest.raises(ImportError):
        from backend.domain.models import Vote  # noqa: F401


def test_scoring_module_does_not_exist():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("backend.domain.scoring")


def test_duplicate_vote_error_not_in_errors():
    import backend.application.errors as err

    assert not hasattr(err, "DuplicateVoteError")


def test_token_transaction_class_removed():
    import backend.domain.models as models

    assert not hasattr(models, "TokenTransaction")


# Repository protocol guards


def test_problem_repository_has_delete_method():
    from backend.domain.repositories import ProblemRepository

    assert hasattr(ProblemRepository, "delete")


def test_problem_repository_has_find_unreviewed_method():
    from backend.domain.repositories import ProblemRepository

    assert hasattr(ProblemRepository, "find_unreviewed")


def test_solution_repository_has_delete_method():
    from backend.domain.repositories import SolutionRepository

    assert hasattr(SolutionRepository, "delete")


def test_solution_repository_has_find_unreviewed_method():
    from backend.domain.repositories import SolutionRepository

    assert hasattr(SolutionRepository, "find_unreviewed")


def test_solution_repository_has_list_by_problem_ranked():
    from backend.domain.repositories import SolutionRepository

    assert hasattr(SolutionRepository, "list_by_problem_ranked")


def test_thread_repository_not_in_repositories():
    import backend.domain.repositories as repos

    assert not hasattr(repos, "ThreadRepository")


def test_comment_repository_not_in_repositories():
    import backend.domain.repositories as repos

    assert not hasattr(repos, "CommentRepository")


def test_vote_repository_not_in_repositories():
    import backend.domain.repositories as repos

    assert not hasattr(repos, "VoteRepository")
