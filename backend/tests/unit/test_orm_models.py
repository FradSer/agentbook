"""Unit tests for unified ORM models (sqlalchemy_models.py) — V3 schema."""
from __future__ import annotations

import pytest


def _column_names(orm_class) -> set[str]:
    return {col.key for col in orm_class.__table__.columns}


def test_problem_orm_has_review_status():
    from backend.infrastructure.persistence.sqlalchemy_models import ProblemORM

    assert "review_status" in _column_names(ProblemORM)


def test_problem_orm_has_review_score():
    from backend.infrastructure.persistence.sqlalchemy_models import ProblemORM

    assert "review_score" in _column_names(ProblemORM)


def test_problem_orm_has_reviewed_at():
    from backend.infrastructure.persistence.sqlalchemy_models import ProblemORM

    assert "reviewed_at" in _column_names(ProblemORM)


def test_problem_orm_has_canonical_solution_id():
    from backend.infrastructure.persistence.sqlalchemy_models import ProblemORM

    assert "canonical_solution_id" in _column_names(ProblemORM)


def test_solution_orm_has_review_status():
    from backend.infrastructure.persistence.sqlalchemy_models import SolutionORM

    assert "review_status" in _column_names(SolutionORM)


def test_solution_orm_has_review_score():
    from backend.infrastructure.persistence.sqlalchemy_models import SolutionORM

    assert "review_score" in _column_names(SolutionORM)


def test_solution_orm_has_reviewed_at():
    from backend.infrastructure.persistence.sqlalchemy_models import SolutionORM

    assert "reviewed_at" in _column_names(SolutionORM)


def test_solution_orm_has_self_parent_check_constraint():
    from sqlalchemy import CheckConstraint
    from backend.infrastructure.persistence.sqlalchemy_models import SolutionORM

    table_args = SolutionORM.__table_args__
    constraints = [
        c for c in SolutionORM.__table__.constraints if isinstance(c, CheckConstraint)
    ]
    has_self_parent_check = any(
        "parent_solution_id" in str(c.sqltext) and "solution_id" in str(c.sqltext)
        for c in constraints
    )
    assert has_self_parent_check, (
        f"Expected CheckConstraint preventing self-parent on SolutionORM, "
        f"found constraints: {[str(c.sqltext) for c in constraints]}"
    )


def test_token_transaction_orm_has_related_solution_id():
    from backend.infrastructure.persistence.sqlalchemy_models import TokenTransactionORM

    assert "related_solution_id" in _column_names(TokenTransactionORM)


def test_token_transaction_orm_has_no_related_comment_id():
    from backend.infrastructure.persistence.sqlalchemy_models import TokenTransactionORM

    assert "related_comment_id" not in _column_names(TokenTransactionORM)


def test_thread_orm_does_not_exist():
    import backend.infrastructure.persistence.sqlalchemy_models as orm

    assert not hasattr(orm, "ThreadORM")


def test_comment_orm_does_not_exist():
    import backend.infrastructure.persistence.sqlalchemy_models as orm

    assert not hasattr(orm, "CommentORM")


def test_vote_orm_does_not_exist():
    import backend.infrastructure.persistence.sqlalchemy_models as orm

    assert not hasattr(orm, "VoteORM")


def test_migration_file_has_upgrade_function():
    """The unification migration must define an upgrade() function."""
    import importlib.util
    import pathlib

    migration_path = pathlib.Path("alembic/versions/f5g6h7i8j9k0_unify_v1_v2.py")
    assert migration_path.exists(), f"Migration file not found: {migration_path}"

    spec = importlib.util.spec_from_file_location("migration", migration_path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    assert hasattr(mod, "upgrade"), "Migration must define upgrade()"


def test_migration_file_downgrade_raises():
    """The unification migration downgrade() must raise NotImplementedError."""
    import importlib.util
    import pathlib

    migration_path = pathlib.Path("alembic/versions/f5g6h7i8j9k0_unify_v1_v2.py")
    if not migration_path.exists():
        pytest.skip("Migration file not yet created")

    spec = importlib.util.spec_from_file_location("migration", migration_path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    with pytest.raises(NotImplementedError):
        mod.downgrade()
