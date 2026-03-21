"""Cache backend protocol definition."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from kg.cache.models import CacheStats


@runtime_checkable
class CacheBackend(Protocol):
    """Protocol for cache backend implementations.

    Backends must implement get, set, delete, clear, and stats.
    """

    def get(self, key: str) -> object | None:
        """Retrieve a cached value by key.

        Args:
            key: Cache key.

        Returns:
            The cached value, or None if not found or expired.
        """
        ...

    def set(self, key: str, value: object, ttl: int | None = None) -> None:
        """Store a value in the cache.

        Args:
            key: Cache key.
            value: Value to cache (must be serializable for Redis).
            ttl: Time-to-live in seconds. Uses default_ttl if None.
        """
        ...

    def delete(self, key: str) -> bool:
        """Remove a key from the cache.

        Args:
            key: Cache key.

        Returns:
            True if the key existed and was removed.
        """
        ...

    def clear(self) -> None:
        """Remove all entries from the cache."""
        ...

    def exists(self, key: str) -> bool:
        """Check if a key exists in the cache (not expired).

        Args:
            key: Cache key.

        Returns:
            True if the key exists and is not expired.
        """
        ...

    @property
    def stats(self) -> CacheStats:
        """Return current cache statistics."""
        ...
