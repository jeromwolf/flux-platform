"""Tests for ResponseCache — TTL-based in-memory GET response cache."""
from __future__ import annotations

import time

import pytest

from gateway.middleware.cache import CacheEntry, ResponseCache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry(body: bytes = b"hello", status: int = 200, created_at: float | None = None) -> CacheEntry:
    """Build a CacheEntry with sensible defaults."""
    return CacheEntry(
        body=body,
        status_code=status,
        headers={"content-type": "application/json"},
        created_at=created_at if created_at is not None else time.monotonic(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestResponseCache:
    """Tests for ResponseCache."""

    @pytest.mark.unit
    def test_cache_miss_returns_none(self):
        """get() on an empty cache returns None."""
        cache = ResponseCache(ttl=60.0)
        result = cache.get("/api/nodes", "")
        assert result is None

    @pytest.mark.unit
    def test_cache_put_and_get(self):
        """put() stores entry; get() returns it with matching body and status."""
        cache = ResponseCache(ttl=60.0)
        body = b'{"nodes": []}'
        cache.put("/api/nodes", "", body, 200, {"content-type": "application/json"})

        entry = cache.get("/api/nodes", "")
        assert entry is not None
        assert entry.body == body
        assert entry.status_code == 200

    @pytest.mark.unit
    def test_cache_expiry(self):
        """Entry is treated as expired once TTL seconds have passed."""
        cache = ResponseCache(ttl=1.0)
        cache.put("/api/nodes", "", b"data", 200, {})

        # Not expired yet
        assert cache.get("/api/nodes", "") is not None

        # Manually age the entry beyond TTL
        key = cache._make_key("/api/nodes", "")
        cache._cache[key].created_at -= 2.0  # simulate 2 seconds elapsed

        assert cache.get("/api/nodes", "") is None

    @pytest.mark.unit
    def test_cache_max_entries_eviction(self):
        """When max_entries is reached, the oldest entry is evicted."""
        cache = ResponseCache(ttl=60.0, max_entries=3)

        # Fill to capacity with distinct timestamps
        for i in range(3):
            path = f"/api/item/{i}"
            cache.put(path, "", f"body{i}".encode(), 200, {})
            # Ensure monotonically increasing created_at
            key = cache._make_key(path, "")
            cache._cache[key].created_at = time.monotonic() + i * 0.001

        assert cache.size == 3

        # Add a 4th entry — oldest (item/0) should be evicted
        cache.put("/api/item/3", "", b"body3", 200, {})

        assert cache.size == 3
        # The newly inserted entry must be present
        assert cache.get("/api/item/3", "") is not None

    @pytest.mark.unit
    def test_cache_skip_error_responses(self):
        """Responses with status >= 400 must never be cached."""
        cache = ResponseCache(ttl=60.0)
        cache.put("/api/bad", "", b"not found", 404, {})
        cache.put("/api/error", "", b"server error", 500, {})

        assert cache.get("/api/bad", "") is None
        assert cache.get("/api/error", "") is None
        assert cache.size == 0

    @pytest.mark.unit
    def test_cache_invalidate_all(self):
        """invalidate() with no argument clears all entries and returns count."""
        cache = ResponseCache(ttl=60.0)
        for i in range(5):
            cache.put(f"/api/item/{i}", "", b"data", 200, {})

        count = cache.invalidate()
        assert count == 5
        assert cache.size == 0

    @pytest.mark.unit
    def test_cache_cleanup_expired(self):
        """cleanup_expired() removes stale entries and returns the count removed."""
        cache = ResponseCache(ttl=60.0)

        # Two fresh entries
        cache.put("/api/fresh1", "", b"fresh", 200, {})
        cache.put("/api/fresh2", "", b"fresh", 200, {})

        # One stale entry (manually aged)
        cache.put("/api/stale", "", b"stale", 200, {})
        stale_key = cache._make_key("/api/stale", "")
        cache._cache[stale_key].created_at -= 120.0  # 2 minutes ago

        removed = cache.cleanup_expired()
        assert removed == 1
        assert cache.size == 2
        assert cache.get("/api/fresh1", "") is not None
        assert cache.get("/api/fresh2", "") is not None
        assert cache.get("/api/stale", "") is None

    @pytest.mark.unit
    def test_cache_size(self):
        """size property reflects the current number of cached entries."""
        cache = ResponseCache(ttl=60.0)
        assert cache.size == 0

        cache.put("/api/a", "", b"a", 200, {})
        assert cache.size == 1

        cache.put("/api/b", "", b"b", 200, {})
        assert cache.size == 2

        cache.invalidate()
        assert cache.size == 0

    @pytest.mark.unit
    def test_cache_query_string_differentiates_entries(self):
        """Entries for the same path but different query strings are stored separately."""
        cache = ResponseCache(ttl=60.0)
        cache.put("/api/search", "q=foo", b"foo results", 200, {})
        cache.put("/api/search", "q=bar", b"bar results", 200, {})

        assert cache.size == 2
        entry_foo = cache.get("/api/search", "q=foo")
        entry_bar = cache.get("/api/search", "q=bar")
        assert entry_foo is not None and entry_foo.body == b"foo results"
        assert entry_bar is not None and entry_bar.body == b"bar results"
