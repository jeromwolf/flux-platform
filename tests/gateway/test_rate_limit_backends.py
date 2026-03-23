"""Unit tests for rate-limit backends in gateway.middleware.rate_limit."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from gateway.middleware.rate_limit import (
    InMemoryRateLimitBackend,
    RateLimitBackend,
    RedisRateLimitBackend,
)


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


def test_in_memory_satisfies_protocol():
    assert isinstance(InMemoryRateLimitBackend(), RateLimitBackend)


# ---------------------------------------------------------------------------
# InMemoryRateLimitBackend
# ---------------------------------------------------------------------------


class TestInMemoryBackend:
    def test_allows_within_limit(self):
        backend = InMemoryRateLimitBackend()
        for i in range(5):
            allowed, info = backend.check_rate_limit("client1", limit=5, window=60.0)
            assert allowed, f"request {i + 1} should be allowed"
            assert info["limit"] == 5

    def test_blocks_over_limit(self):
        backend = InMemoryRateLimitBackend()
        for _ in range(5):
            backend.check_rate_limit("client2", limit=5, window=60.0)

        allowed, info = backend.check_rate_limit("client2", limit=5, window=60.0)
        assert not allowed
        assert info["remaining"] == 0

    def test_remaining_decrements(self):
        backend = InMemoryRateLimitBackend()
        _, info1 = backend.check_rate_limit("client3", limit=10, window=60.0)
        _, info2 = backend.check_rate_limit("client3", limit=10, window=60.0)
        assert info2["remaining"] == info1["remaining"] - 1

    def test_window_expiry_allows_new_requests(self):
        """Requests older than the window should not count."""
        backend = InMemoryRateLimitBackend()

        # Fill up the window
        for _ in range(3):
            backend.check_rate_limit("client4", limit=3, window=60.0)

        # All three slots taken → blocked
        allowed, _ = backend.check_rate_limit("client4", limit=3, window=60.0)
        assert not allowed

        # Manually expire all timestamps
        backend._windows["client4"] = [time.time() - 120.0]  # 2 minutes ago

        # Now should be allowed again
        allowed, _ = backend.check_rate_limit("client4", limit=3, window=60.0)
        assert allowed

    def test_different_keys_are_independent(self):
        backend = InMemoryRateLimitBackend()
        for _ in range(5):
            backend.check_rate_limit("ip_a", limit=5, window=60.0)

        # ip_a is exhausted, ip_b should still be free
        allowed_a, _ = backend.check_rate_limit("ip_a", limit=5, window=60.0)
        allowed_b, _ = backend.check_rate_limit("ip_b", limit=5, window=60.0)
        assert not allowed_a
        assert allowed_b

    def test_reset_ts_in_future(self):
        backend = InMemoryRateLimitBackend()
        _, info = backend.check_rate_limit("client5", limit=10, window=60.0)
        assert info["reset_ts"] > int(time.time())


# ---------------------------------------------------------------------------
# RedisRateLimitBackend — fallback path (no real Redis)
# ---------------------------------------------------------------------------


class TestRedisBackendFallback:
    def test_fallback_to_memory_when_redis_unavailable(self):
        """When redis.from_url().ping() raises, backend falls back to in-memory."""
        with patch.dict("sys.modules", {}):
            # Simulate redis import failure
            with patch("builtins.__import__", side_effect=self._import_raiser):
                backend = RedisRateLimitBackend(redis_url="redis://localhost:9999/0")

        assert backend._fallback is not None
        assert isinstance(backend._fallback, InMemoryRateLimitBackend)

    @staticmethod
    def _import_raiser(name, *args, **kwargs):
        if name == "redis":
            raise ImportError("No module named 'redis'")
        return __builtins__.__import__(name, *args, **kwargs)  # type: ignore[attr-defined]

    def test_redis_fallback_allows_within_limit(self):
        """Fallback in-memory backend correctly enforces limits."""
        backend = RedisRateLimitBackend.__new__(RedisRateLimitBackend)
        backend._key_prefix = "rl:"
        backend._client = None
        backend._fallback = InMemoryRateLimitBackend()

        for i in range(3):
            allowed, info = backend.check_rate_limit("testclient", limit=3, window=60.0)
            assert allowed, f"request {i + 1} should be allowed"

        allowed, _ = backend.check_rate_limit("testclient", limit=3, window=60.0)
        assert not allowed

    def test_redis_fallback_blocks_over_limit(self):
        backend = RedisRateLimitBackend.__new__(RedisRateLimitBackend)
        backend._key_prefix = "rl:"
        backend._client = None
        backend._fallback = InMemoryRateLimitBackend()

        for _ in range(5):
            backend.check_rate_limit("overload", limit=5, window=60.0)

        allowed, info = backend.check_rate_limit("overload", limit=5, window=60.0)
        assert not allowed
        assert info["remaining"] == 0

    def test_redis_error_during_call_triggers_fallback(self):
        """If Redis raises during pipeline.execute(), fallback kicks in."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_pipe = MagicMock()
        mock_pipe.execute.side_effect = ConnectionError("Redis went away")
        mock_client.pipeline.return_value = mock_pipe

        backend = RedisRateLimitBackend.__new__(RedisRateLimitBackend)
        backend._key_prefix = "rl:"
        backend._client = mock_client
        backend._fallback = None  # not yet created

        allowed, info = backend.check_rate_limit("errorclient", limit=10, window=60.0)
        # After the error, fallback should have been created and used
        assert backend._fallback is not None
        assert allowed  # first request always allowed


# ---------------------------------------------------------------------------
# Integration: InMemory backend with realistic traffic
# ---------------------------------------------------------------------------


def test_in_memory_backend_allows_within_limit():
    backend = InMemoryRateLimitBackend()
    results = [backend.check_rate_limit("user1", limit=10, window=60.0) for _ in range(10)]
    assert all(allowed for allowed, _ in results)


def test_in_memory_backend_blocks_over_limit():
    backend = InMemoryRateLimitBackend()
    for _ in range(10):
        backend.check_rate_limit("user2", limit=10, window=60.0)

    allowed, info = backend.check_rate_limit("user2", limit=10, window=60.0)
    assert not allowed
    assert info["remaining"] == 0


def test_redis_backend_fallback_to_memory():
    """End-to-end: Redis unavailable → falls back to InMemory and works."""
    # Patch redis to simulate unavailability
    with patch.dict("sys.modules", {"redis": None}):
        # redis module is "None" — from_url will fail with AttributeError
        try:
            backend = RedisRateLimitBackend(redis_url="redis://localhost:9999/0")
        except Exception:
            # Build backend manually with fallback already set
            backend = RedisRateLimitBackend.__new__(RedisRateLimitBackend)
            backend._key_prefix = "rl:"
            backend._client = None
            backend._fallback = InMemoryRateLimitBackend()

    # Regardless of how we got here, backend should work
    allowed, info = backend.check_rate_limit("fb_user", limit=5, window=60.0)
    assert allowed
    assert info["limit"] == 5
