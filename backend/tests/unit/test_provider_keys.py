"""Tests for shared round-robin key selection."""

from __future__ import annotations

import pytest

from shared.provider_keys import RoundRobin, parse_keys


def test_parse_keys_handles_none_single_and_list():
    assert parse_keys(None) == []
    assert parse_keys("") == []
    assert parse_keys("solo") == ["solo"]
    assert parse_keys(" a , b ,, c ") == ["a", "b", "c"]


def test_round_robin_cycles_and_wraps():
    rr = RoundRobin(["k1", "k2", "k3"])
    assert [rr.next() for _ in range(7)] == ["k1", "k2", "k3", "k1", "k2", "k3", "k1"]


def test_round_robin_single_key_repeats():
    rr = RoundRobin(["only"])
    assert [rr.next() for _ in range(3)] == ["only", "only", "only"]


def test_round_robin_empty_is_falsy_and_raises():
    rr = RoundRobin([])
    assert not rr
    with pytest.raises(ValueError):
        rr.next()
