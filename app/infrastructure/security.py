from __future__ import annotations

import hashlib
import secrets

from app.core.config import settings


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    suffix = secrets.token_urlsafe(24)
    return f"{settings.api_key_prefix}{suffix}"
