"""Bearer scheme parsing — pins RFC 7235 §2.1 case-insensitivity.

The legacy implementation rejected lowercase ``bearer`` / uppercase
``BEARER`` and folded every failure mode into the same misleading
``"provide Bearer token"`` message. These tests pin both the
case-insensitive scheme parsing and the per-failure-kind diagnostics so
calling agents can recover automatically (e.g. retry only when the fix
is on their side).
"""

from __future__ import annotations

import pytest

from backend.core.auth import (
    BearerErrorKind,
    parse_bearer_token,
)


class TestParseBearerTokenCaseInsensitive:
    """RFC 7235 §2.1 — the scheme name is case-insensitive."""

    @pytest.mark.parametrize(
        "header",
        [
            "Bearer ak_canonical",
            "bearer ak_canonical",
            "BEARER ak_canonical",
            "BeArEr ak_canonical",
            "  bearer   ak_canonical  ",
        ],
    )
    def test_accepts_any_scheme_capitalisation(self, header: str) -> None:
        assert parse_bearer_token(header).token == "ak_canonical"

    def test_required_prefix_still_enforced(self) -> None:
        good = parse_bearer_token("bearer ak_token", required_prefix="ak_")
        assert good.ok and good.token == "ak_token"
        bad = parse_bearer_token("bearer sk_token", required_prefix="ak_")
        assert not bad.ok and bad.error_kind is BearerErrorKind.WRONG_PREFIX

    def test_missing_header_yields_missing_error(self) -> None:
        assert parse_bearer_token(None).error_kind is BearerErrorKind.MISSING_HEADER
        assert parse_bearer_token("").error_kind is BearerErrorKind.MISSING_HEADER

    def test_non_bearer_scheme_yields_wrong_scheme_error(self) -> None:
        assert (
            parse_bearer_token("Basic dXNlcjpwYXNz").error_kind
            is BearerErrorKind.WRONG_SCHEME
        )


class TestParseBearerToken:
    """``parse_bearer_token`` exposes the failure mode for actionable 401s."""

    def test_canonical_bearer_yields_ok_result(self) -> None:
        result = parse_bearer_token("Bearer ak_canonical", required_prefix="ak_")
        assert result.ok is True
        assert result.token == "ak_canonical"
        assert result.error_kind is None
        assert result.detail is None

    @pytest.mark.parametrize("header", ["bearer ak_x", "BEARER ak_x", "BeArEr ak_x"])
    def test_non_canonical_capitalisation_yields_ok_result(self, header: str) -> None:
        result = parse_bearer_token(header, required_prefix="ak_")
        assert result.ok is True
        assert result.token == "ak_x"

    def test_missing_header_yields_missing_kind(self) -> None:
        result = parse_bearer_token(None, required_prefix="ak_")
        assert result.ok is False
        assert result.token is None
        assert result.error_kind is BearerErrorKind.MISSING_HEADER
        assert "Authorization header required" in result.detail

    def test_blank_header_yields_missing_kind(self) -> None:
        result = parse_bearer_token("   ", required_prefix="ak_")
        assert result.error_kind is BearerErrorKind.MISSING_HEADER

    def test_wrong_scheme_yields_wrong_scheme_kind(self) -> None:
        result = parse_bearer_token("Basic dXNlcjpwYXNz", required_prefix="ak_")
        assert result.ok is False
        assert result.token is None
        assert result.error_kind is BearerErrorKind.WRONG_SCHEME
        assert "Bearer scheme required" in result.detail

    def test_empty_token_after_scheme_yields_empty_token_kind(self) -> None:
        result = parse_bearer_token("Bearer    ", required_prefix="ak_")
        assert result.error_kind is BearerErrorKind.EMPTY_TOKEN
        assert "token is empty" in result.detail

    def test_wrong_prefix_yields_wrong_prefix_kind(self) -> None:
        result = parse_bearer_token("Bearer sk_otherprovider", required_prefix="ak_")
        assert result.ok is False
        assert result.token is None
        assert result.error_kind is BearerErrorKind.WRONG_PREFIX
        assert "API key must start with 'ak_'" in result.detail

    def test_no_required_prefix_accepts_any_token(self) -> None:
        result = parse_bearer_token("bearer eyJabc.def", required_prefix=None)
        assert result.ok is True
        assert result.token == "eyJabc.def"
