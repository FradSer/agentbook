"""Unit tests for ORM models (sqlalchemy_models.py)."""

from __future__ import annotations

import importlib.util
import pathlib

import pytest


def _column_names(orm_class) -> set[str]:
    return {col.key for col in orm_class.__table__.columns}


def _load_migration():
    migration_path = pathlib.Path("alembic/versions/f5g6h7i8j9k0_unify_v1_v2.py")
    if not migration_path.exists():
        pytest.skip("Migration file not yet created")
    spec = importlib.util.spec_from_file_location("migration", migration_path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# Column presence checks


@pytest.mark.parametrize(
    "column",
    ["review_status", "review_score", "reviewed_at", "canonical_solution_id"],
)
def test_problem_orm_has_column(column: str) -> None:
    from backend.infrastructure.persistence.sqlalchemy_models import ProblemORM

    assert column in _column_names(ProblemORM)


@pytest.mark.parametrize(
    "column",
    ["review_status", "review_score", "reviewed_at"],
)
def test_solution_orm_has_column(column: str) -> None:
    from backend.infrastructure.persistence.sqlalchemy_models import SolutionORM

    assert column in _column_names(SolutionORM)


# Removed ORM symbols


@pytest.mark.parametrize(
    "orm_name",
    ["TokenTransactionORM", "ThreadORM", "CommentORM", "VoteORM"],
)
def test_removed_orm_does_not_exist(orm_name: str) -> None:
    import backend.infrastructure.persistence.sqlalchemy_models as orm

    assert not hasattr(orm, orm_name)


def test_agent_orm_has_no_token_balance_column() -> None:
    from backend.infrastructure.persistence.sqlalchemy_models import AgentORM

    assert "token_balance" not in _column_names(AgentORM)


# Solution self-parent constraint


def test_solution_orm_has_self_parent_check_constraint() -> None:
    from sqlalchemy import CheckConstraint

    from backend.infrastructure.persistence.sqlalchemy_models import SolutionORM

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


# Migration file checks


def test_migration_file_has_upgrade_function() -> None:
    """The unification migration must define an upgrade() function."""
    mod = _load_migration()
    assert hasattr(mod, "upgrade"), "Migration must define upgrade()"


def test_migration_file_downgrade_raises() -> None:
    """The unification migration downgrade() must raise NotImplementedError."""
    mod = _load_migration()
    with pytest.raises(NotImplementedError):
        mod.downgrade()
