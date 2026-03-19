"""Unit tests for unified domain models (V3 — Problem/Solution/Outcome only)."""
from __future__ import annotations

import importlib
import sys
from uuid import uuid4

import pytest


def test_problem_has_review_fields():
    from app.domain.models import Problem

    p = Problem(author_id=uuid4(), description="Docker Alpine numpy error")
    assert p.review_status is None
    assert p.review_score is None
    assert p.reviewed_at is None


def test_problem_has_canonical_solution_id():
    from app.domain.models import Problem

    p = Problem(author_id=uuid4(), description="Some error")
    assert p.canonical_solution_id is None


def test_problem_has_required_tracking_fields():
    from app.domain.models import Problem

    p = Problem(author_id=uuid4(), description="Some error")
    assert p.best_confidence == 0.0
    assert p.solution_count == 0
    assert p.version == 1
    assert p.last_activity_at is not None


def test_solution_default_confidence_is_0_3():
    from app.domain.models import Solution

    s = Solution(problem_id=uuid4(), author_id=uuid4(), content="Fix it")
    assert s.confidence == 0.3


def test_solution_author_verified_sets_confidence_to_0_5():
    from app.domain.models import Solution

    s = Solution(
        problem_id=uuid4(), author_id=uuid4(), content="Fix it", author_verified=True
    )
    assert s.confidence == 0.5


def test_solution_has_review_fields():
    from app.domain.models import Solution

    s = Solution(problem_id=uuid4(), author_id=uuid4(), content="Fix it")
    assert s.review_status is None
    assert s.review_score is None
    assert s.reviewed_at is None


def test_solution_has_outcome_tracking_fields():
    from app.domain.models import Solution

    s = Solution(problem_id=uuid4(), author_id=uuid4(), content="Fix it")
    assert s.outcome_count == 0
    assert s.success_count == 0
    assert s.failure_count == 0
    assert s.parent_solution_id is None
    assert s.canonical_id is None


def test_thread_not_importable():
    with pytest.raises(ImportError):
        from app.domain.models import Thread  # noqa: F401


def test_comment_not_importable():
    with pytest.raises(ImportError):
        from app.domain.models import Comment  # noqa: F401


def test_vote_not_importable():
    with pytest.raises(ImportError):
        from app.domain.models import Vote  # noqa: F401


def test_scoring_module_does_not_exist():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.domain.scoring")


def test_duplicate_vote_error_not_in_errors():
    import app.application.errors as err

    assert not hasattr(err, "DuplicateVoteError")


def test_token_transaction_has_related_solution_id():
    from app.domain.models import TokenTransaction

    tx = TokenTransaction(
        agent_id=uuid4(),
        amount=5,
        tx_type="outcome_reward",
        related_solution_id=None,
        description="reward",
    )
    assert tx.related_solution_id is None


def test_token_transaction_has_no_related_comment_id():
    from app.domain.models import TokenTransaction

    tx = TokenTransaction(
        agent_id=uuid4(),
        amount=5,
        tx_type="outcome_reward",
        related_solution_id=None,
        description="reward",
    )
    assert not hasattr(tx, "related_comment_id")


def test_problem_repository_has_delete_method():
    from app.domain.repositories import ProblemRepository

    assert hasattr(ProblemRepository, "delete")


def test_problem_repository_has_find_unreviewed_method():
    from app.domain.repositories import ProblemRepository

    assert hasattr(ProblemRepository, "find_unreviewed")


def test_solution_repository_has_delete_method():
    from app.domain.repositories import SolutionRepository

    assert hasattr(SolutionRepository, "delete")


def test_solution_repository_has_find_unreviewed_method():
    from app.domain.repositories import SolutionRepository

    assert hasattr(SolutionRepository, "find_unreviewed")


def test_solution_repository_has_list_by_problem_ranked():
    from app.domain.repositories import SolutionRepository

    assert hasattr(SolutionRepository, "list_by_problem_ranked")


def test_thread_repository_not_in_repositories():
    import app.domain.repositories as repos

    assert not hasattr(repos, "ThreadRepository")


def test_comment_repository_not_in_repositories():
    import app.domain.repositories as repos

    assert not hasattr(repos, "CommentRepository")


def test_vote_repository_not_in_repositories():
    import app.domain.repositories as repos

    assert not hasattr(repos, "VoteRepository")
