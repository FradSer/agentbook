from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any


class TTLCache:
    """Thread-safe LRU cache with per-entry TTL expiry.

    Used by `AgentbookService.search_problems` to absorb identical repeat
    queries from agent retry loops. Entries expire after `ttl` seconds and
    the oldest entries are evicted once `maxsize` is reached.
    """

    def __init__(
        self,
        maxsize: int = 256,
        ttl: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._maxsize = maxsize
        self._ttl = ttl
        self._clock = clock
        self._store: OrderedDict[tuple, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: tuple) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at <= self._clock():
                self._store.pop(key, None)
                return None
            self._store.move_to_end(key)
            return value

    def set(self, key: tuple, value: Any) -> None:
        with self._lock:
            expires_at = self._clock() + self._ttl
            self._store[key] = (expires_at, value)
            self._store.move_to_end(key)
            while len(self._store) > self._maxsize:
                self._store.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
