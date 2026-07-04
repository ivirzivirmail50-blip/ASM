"""Thread-safe in-memory cache with TTL.

Simple dict-based cache for stats and export progress.
Invalidation by prefix.
"""
from __future__ import annotations

import threading
import time
from typing import Any


class _Cache:
    """Thread-safe in-memory cache with TTL."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}  # key → (value, expires_at)
        self._lock = threading.Lock()

    def set(self, key: str, value: Any, ttl_seconds: int = 60) -> None:
        """Set a cache entry with TTL in seconds."""
        with self._lock:
            self._store[key] = (value, time.time() + ttl_seconds)

    def get(self, key: str) -> Any | None:
        """Get a cache entry. Returns None if expired or missing."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.time() > expires_at:
                del self._store[key]
                return None
            return value

    def invalidate(self, prefix: str) -> int:
        """Invalidate all keys starting with prefix. Returns count removed."""
        removed = 0
        with self._lock:
            keys_to_delete = [k for k in self._store if k.startswith(prefix)]
            for k in keys_to_delete:
                del self._store[k]
                removed += 1
        return removed

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        """Return number of entries (including expired)."""
        with self._lock:
            return len(self._store)


# Singleton instance
cache = _Cache()


def cached(key: str, ttl_seconds: int = 60):
    """Decorator: cache the result of a function call.

    Usage:
        @cached("stats:overall_counts", ttl_seconds=60)
        def overall_counts():
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            cached_val = cache.get(key)
            if cached_val is not None:
                return cached_val
            result = func(*args, **kwargs)
            cache.set(key, result, ttl_seconds)
            return result
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator
