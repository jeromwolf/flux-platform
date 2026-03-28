"""Simple TTL-based response cache for GET requests."""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field


@dataclass
class CacheEntry:
    body: bytes
    status_code: int
    headers: dict[str, str]
    created_at: float

    def is_expired(self, ttl: float) -> bool:
        return time.monotonic() - self.created_at > ttl


@dataclass
class ResponseCache:
    """In-memory LRU-ish response cache with TTL expiration.

    Only caches GET requests. POST/PUT/DELETE are never cached.
    Cache keys include the full URL path + query string.
    """

    ttl: float = 60.0          # seconds
    max_entries: int = 256
    _cache: dict[str, CacheEntry] = field(default_factory=dict, init=False)
    _path_index: dict[str, set[str]] = field(default_factory=dict, init=False)

    def _make_key(self, path: str, query: str = "") -> str:
        raw = f"GET:{path}?{query}" if query else f"GET:{path}"
        return hashlib.md5(raw.encode()).hexdigest()  # noqa: S324

    def get(self, path: str, query: str = "") -> CacheEntry | None:
        key = self._make_key(path, query)
        entry = self._cache.get(key)
        if entry is None:
            return None
        if entry.is_expired(self.ttl):
            self._remove_from_index(key)
            del self._cache[key]
            return None
        return entry

    def put(self, path: str, query: str, body: bytes, status_code: int, headers: dict[str, str]) -> None:
        # Only cache successful responses
        if status_code >= 400:
            return

        key = self._make_key(path, query)

        # Evict oldest entries if at capacity
        if len(self._cache) >= self.max_entries and key not in self._cache:
            oldest_key = min(self._cache, key=lambda k: self._cache[k].created_at)
            self._remove_from_index(oldest_key)
            del self._cache[oldest_key]

        self._cache[key] = CacheEntry(
            body=body,
            status_code=status_code,
            headers=headers,
            created_at=time.monotonic(),
        )
        # Update path index
        if path not in self._path_index:
            self._path_index[path] = set()
        self._path_index[path].add(key)

    def _remove_from_index(self, key: str) -> None:
        """Remove a key from the path index."""
        empty_paths: list[str] = []
        for path, keys in self._path_index.items():
            keys.discard(key)
            if not keys:
                empty_paths.append(path)
        for path in empty_paths:
            del self._path_index[path]

    def invalidate(self, path: str | None = None) -> int:
        """Invalidate cache entries. If path given, invalidate matching entries; else clear all."""
        if path is None:
            count = len(self._cache)
            self._cache.clear()
            self._path_index.clear()
            return count

        # Selective invalidation: remove entries whose path starts with the given prefix
        keys_to_remove: set[str] = set()
        paths_to_remove: list[str] = []
        for cached_path, keys in self._path_index.items():
            if cached_path == path or cached_path.startswith(path):
                keys_to_remove.update(keys)
                paths_to_remove.append(cached_path)

        for key in keys_to_remove:
            self._cache.pop(key, None)
        for p in paths_to_remove:
            del self._path_index[p]

        return len(keys_to_remove)

    @property
    def size(self) -> int:
        return len(self._cache)

    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count removed."""
        expired = [k for k, v in self._cache.items() if v.is_expired(self.ttl)]
        for k in expired:
            self._remove_from_index(k)
            del self._cache[k]
        return len(expired)
