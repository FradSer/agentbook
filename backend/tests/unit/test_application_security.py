"""Unit tests for backend.application.security.

These helpers gate write traffic. The hash function MUST be a stable,
deterministic SHA-256 of the bytes -- changing it silently invalidates
every persisted ``Agent.api_key_hash`` row.
"""

from __future__ import annotations

import hashlib

from backend.application.security import generate_api_key, hash_api_key
from backend.core.config import settings


def test_hash_api_key_is_sha256_hex_of_utf8_bytes() -> None:
    api_key = "ak_example_key_value"
    expected = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    assert hash_api_key(api_key) == expected
    # 64-char lowercase hex.
    assert len(hash_api_key(api_key)) == 64
    assert hash_api_key(api_key) == hash_api_key(api_key)


def test_hash_api_key_is_collision_resistant_for_distinct_inputs() -> None:
    assert hash_api_key("ak_a") != hash_api_key("ak_b")
    # A single trailing newline must produce a different hash.
    assert hash_api_key("ak_a") != hash_api_key("ak_a\n")


def test_generate_api_key_uses_configured_prefix() -> None:
    key = generate_api_key()
    assert key.startswith(settings.api_key_prefix)


def test_generate_api_key_is_unique_across_calls() -> None:
    keys = {generate_api_key() for _ in range(50)}
    assert len(keys) == 50


def test_generate_api_key_suffix_is_url_safe_base64() -> None:
    key = generate_api_key()
    suffix = key[len(settings.api_key_prefix) :]
    # token_urlsafe(24) produces 32 chars from URL-safe alphabet.
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
    assert len(suffix) == 32
    assert set(suffix).issubset(allowed)
