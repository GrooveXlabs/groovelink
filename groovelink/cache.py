"""Simple in-memory response cache for circuit fallback."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class _CacheEntry:
    data: Any
    timestamp: float
    ttl: float


class ResponseCache:
    """Thread-safe in-memory cache with TTL support."""

    def __init__(self, default_ttl: float = 300.0) -> None:
        self._default_ttl = default_ttl
        self._store: dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any:
        """Retrieve a cached value if not expired."""
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            if time.monotonic() - entry.timestamp > entry.ttl:
                del self._store[key]
                return None
            return entry.data

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store a value in the cache."""
        with self._lock:
            self._store[key] = _CacheEntry(
                data=value,
                timestamp=time.monotonic(),
                ttl=ttl if ttl is not None else self._default_ttl,
            )

    def delete(self, key: str) -> None:
        """Remove a key from the cache."""
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._store.clear()

    def keys(self) -> list[str]:
        """Return all non-expired keys."""
        now = time.monotonic()
        with self._lock:
            expired = [k for k, v in self._store.items() if now - v.timestamp > v.ttl]
            for k in expired:
                del self._store[k]
            return list(self._store.keys())
