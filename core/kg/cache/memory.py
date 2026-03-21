"""In-memory cache backend.

Thread-safe LRU-like cache with TTL support.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from typing import Any

from kg.cache.models import CacheConfig, CacheEntry, CacheStats

logger = logging.getLogger(__name__)


class InMemoryCache:
    """In-memory cache with TTL and LRU eviction.

    Thread-safe implementation using a lock and OrderedDict for
    approximate LRU ordering.

    Satisfies the CacheBackend protocol via duck typing.

    Args:
        config: Cache configuration. Defaults to CacheConfig().

    Example::

        cache = InMemoryCache()
        cache.set("key", "value", ttl=60)
        result = cache.get("key")  # "value"
    """

    def __init__(self, config: CacheConfig | None = None) -> None:
        self._config = config or CacheConfig()
        self._data: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._stats = CacheStats()

    def get(self, key: str) -> object | None:
        """Retrieve a cached value, returning None if missing or expired."""
        prefixed = self._prefix(key)
        with self._lock:
            entry = self._data.get(prefixed)
            if entry is None:
                self._stats.misses += 1
                return None
            if entry.is_expired:
                del self._data[prefixed]
                self._stats.expirations += 1
                self._stats.misses += 1
                return None
            # Move to end (most recently used)
            self._data.move_to_end(prefixed)
            self._stats.hits += 1
            return entry.value

    def set(self, key: str, value: object, ttl: int | None = None) -> None:
        """Store a value with optional TTL override."""
        prefixed = self._prefix(key)
        effective_ttl = ttl if ttl is not None else self._config.default_ttl
        entry = CacheEntry(
            key=prefixed,
            value=value,
            created_at=time.monotonic(),
            ttl=effective_ttl,
        )
        with self._lock:
            if prefixed in self._data:
                del self._data[prefixed]
            self._data[prefixed] = entry
            self._stats.sets += 1
            self._evict_if_needed()

    def delete(self, key: str) -> bool:
        """Remove a key from the cache."""
        prefixed = self._prefix(key)
        with self._lock:
            if prefixed in self._data:
                del self._data[prefixed]
                return True
            return False

    def clear(self) -> None:
        """Remove all entries."""
        with self._lock:
            self._data.clear()

    def exists(self, key: str) -> bool:
        """Check if a non-expired entry exists."""
        prefixed = self._prefix(key)
        with self._lock:
            entry = self._data.get(prefixed)
            if entry is None:
                return False
            if entry.is_expired:
                del self._data[prefixed]
                self._stats.expirations += 1
                return False
            return True

    @property
    def stats(self) -> CacheStats:
        """Current cache statistics."""
        return self._stats

    @property
    def size(self) -> int:
        """Current number of entries (including potentially expired)."""
        return len(self._data)

    def _prefix(self, key: str) -> str:
        """Add the configured key prefix."""
        return f"{self._config.key_prefix}{key}"

    def _evict_if_needed(self) -> None:
        """Evict oldest entries if over max_size. Must hold lock."""
        while len(self._data) > self._config.max_size:
            self._data.popitem(last=False)
            self._stats.evictions += 1
