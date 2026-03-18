from __future__ import annotations

from app.infrastructure.persistence.sqlalchemy_models import FlexibleVector

_col = FlexibleVector(3)


def test_flexible_vector_parses_pgvector_string() -> None:
    assert _col.process_result_value("[0.1, 0.2, 0.3]", None) == [0.1, 0.2, 0.3]


def test_flexible_vector_keeps_list() -> None:
    assert _col.process_result_value([0.1, 0.2, 0.3], None) == [0.1, 0.2, 0.3]


def test_flexible_vector_handles_none() -> None:
    assert _col.process_result_value(None, None) is None


def test_flexible_vector_handles_empty_string() -> None:
    assert _col.process_result_value("[]", None) == []
