"""Tests for ResponseCache selective invalidation."""
import pytest

from gateway.middleware.cache import ResponseCache

pytestmark = pytest.mark.unit


class TestResponseCacheInvalidation:
    def test_selective_invalidation_by_exact_path(self):
        cache = ResponseCache(ttl=60.0)
        cache.put("/api/v1/nodes", "", b'{"nodes":[]}', 200, {"content-type": "application/json"})
        cache.put("/api/v1/schema", "", b'{"labels":[]}', 200, {"content-type": "application/json"})

        removed = cache.invalidate("/api/v1/nodes")
        assert removed == 1
        assert cache.get("/api/v1/nodes", "") is None
        assert cache.get("/api/v1/schema", "") is not None

    def test_selective_invalidation_by_prefix(self):
        cache = ResponseCache(ttl=60.0)
        cache.put("/api/v1/nodes", "limit=10", b'[]', 200, {})
        cache.put("/api/v1/nodes", "limit=20", b'[]', 200, {})
        cache.put("/api/v1/schema", "", b'{}', 200, {})

        removed = cache.invalidate("/api/v1/nodes")
        assert removed == 2
        assert cache.size == 1

    def test_full_invalidation(self):
        cache = ResponseCache(ttl=60.0)
        cache.put("/a", "", b'1', 200, {})
        cache.put("/b", "", b'2', 200, {})

        removed = cache.invalidate()
        assert removed == 2
        assert cache.size == 0

    def test_invalidate_nonexistent_path_returns_zero(self):
        cache = ResponseCache(ttl=60.0)
        cache.put("/a", "", b'1', 200, {})

        removed = cache.invalidate("/nonexistent")
        assert removed == 0
        assert cache.size == 1

    def test_eviction_cleans_index(self):
        cache = ResponseCache(ttl=60.0, max_entries=2)
        cache.put("/a", "", b'1', 200, {})
        cache.put("/b", "", b'2', 200, {})
        cache.put("/c", "", b'3', 200, {})  # should evict oldest

        assert cache.size == 2
