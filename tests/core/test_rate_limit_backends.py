"""Tests for rate limit backends (InMemory and Redis)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from kg.api.middleware.rate_limit import (
    InMemoryRateLimitBackend,
    RedisRateLimitBackend,
    RateLimitBackend,
)


@pytest.mark.unit
class TestInMemoryRateLimitBackend:
    """Test the in-memory token-bucket rate limit backend."""

    def test_is_protocol(self) -> None:
        backend = InMemoryRateLimitBackend()
        assert isinstance(backend, RateLimitBackend)

    def test_allows_within_limit(self) -> None:
        backend = InMemoryRateLimitBackend()
        allowed, headers = backend.check_limit("user1", max_requests=5, window_seconds=60)
        assert allowed is True

    def test_blocks_over_limit(self) -> None:
        backend = InMemoryRateLimitBackend()
        # Exhaust tokens with refill_rate=0 to ensure no refill during test
        # Use a small window (large bucket) to be safe; consume all 5 tokens
        for _ in range(5):
            backend.check_limit("user1", max_requests=5, window_seconds=600)
        # 6th request should be blocked (no time to refill in a tight loop)
        # Use a no-refill scenario: capacity=1 to guarantee block
        backend2 = InMemoryRateLimitBackend()
        backend2.check_limit("u2", max_requests=1, window_seconds=600)
        allowed, _headers = backend2.check_limit("u2", max_requests=1, window_seconds=600)
        assert allowed is False

    def test_returns_rate_limit_headers(self) -> None:
        backend = InMemoryRateLimitBackend()
        _allowed, headers = backend.check_limit("user1", max_requests=10, window_seconds=60)
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers
        assert headers["X-RateLimit-Limit"] == "10"

    def test_separate_keys_are_independent(self) -> None:
        backend = InMemoryRateLimitBackend()
        # Exhaust user1
        backend.check_limit("user1", max_requests=1, window_seconds=600)
        allowed_u1, _ = backend.check_limit("user1", max_requests=1, window_seconds=600)
        # user2 should still be allowed
        allowed_u2, _ = backend.check_limit("user2", max_requests=1, window_seconds=600)
        assert allowed_u1 is False
        assert allowed_u2 is True

    def test_remaining_decrements(self) -> None:
        backend = InMemoryRateLimitBackend()
        _, h1 = backend.check_limit("u1", max_requests=5, window_seconds=600)
        _, h2 = backend.check_limit("u1", max_requests=5, window_seconds=600)
        remaining1 = int(h1["X-RateLimit-Remaining"])
        remaining2 = int(h2["X-RateLimit-Remaining"])
        assert remaining2 <= remaining1


@pytest.mark.unit
class TestRedisRateLimitBackend:
    """Test the Redis rate limit backend with mocked Redis."""

    def _make_backend(self, execute_return: list) -> tuple[RedisRateLimitBackend, MagicMock]:
        mock_client = MagicMock()
        mock_pipe = MagicMock()
        mock_client.pipeline.return_value = mock_pipe
        mock_pipe.execute.return_value = execute_return
        backend = RedisRateLimitBackend(redis_client=mock_client)
        return backend, mock_client

    def test_is_protocol(self) -> None:
        mock_client = MagicMock()
        backend = RedisRateLimitBackend(redis_client=mock_client)
        assert isinstance(backend, RateLimitBackend)

    def test_allows_within_limit(self) -> None:
        backend, _ = self._make_backend([3, True])  # current=3, limit=5 -> allowed
        allowed, headers = backend.check_limit("user1", max_requests=5, window_seconds=60)
        assert allowed is True
        assert headers["X-RateLimit-Remaining"] == "2"

    def test_blocks_over_limit(self) -> None:
        backend, _ = self._make_backend([6, True])  # current=6, limit=5 -> blocked
        allowed, headers = backend.check_limit("user1", max_requests=5, window_seconds=60)
        assert allowed is False
        assert headers["X-RateLimit-Remaining"] == "0"

    def test_blocks_at_exact_limit(self) -> None:
        backend, _ = self._make_backend([5, True])  # current=5, limit=5 -> allowed (==)
        allowed, _ = backend.check_limit("user1", max_requests=5, window_seconds=60)
        assert allowed is True

    def test_returns_rate_limit_headers(self) -> None:
        backend, _ = self._make_backend([2, True])
        _allowed, headers = backend.check_limit("user1", max_requests=10, window_seconds=60)
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers
        assert headers["X-RateLimit-Limit"] == "10"
        assert headers["X-RateLimit-Reset"] == "60"

    def test_redis_failure_allows_request(self) -> None:
        """Fail-open: Redis errors should allow the request."""
        mock_client = MagicMock()
        mock_pipe = MagicMock()
        mock_client.pipeline.return_value = mock_pipe
        mock_pipe.execute.side_effect = Exception("Redis down")

        backend = RedisRateLimitBackend(redis_client=mock_client)
        allowed, headers = backend.check_limit("user1", max_requests=5, window_seconds=60)
        assert allowed is True

    def test_redis_failure_uses_fallback_backend(self) -> None:
        """After Redis fails, fallback in-memory backend should be initialized."""
        mock_client = MagicMock()
        mock_pipe = MagicMock()
        mock_client.pipeline.return_value = mock_pipe
        mock_pipe.execute.side_effect = Exception("Redis down")

        backend = RedisRateLimitBackend(redis_client=mock_client)
        assert backend._fallback is None
        backend.check_limit("user1", max_requests=5, window_seconds=60)
        assert backend._fallback is not None
        assert isinstance(backend._fallback, InMemoryRateLimitBackend)

    def test_uses_key_prefix(self) -> None:
        """Verify the Redis key uses the configured prefix."""
        mock_client = MagicMock()
        mock_pipe = MagicMock()
        mock_client.pipeline.return_value = mock_pipe
        mock_pipe.execute.return_value = [1, True]

        backend = RedisRateLimitBackend(redis_client=mock_client, key_prefix="test:")
        backend.check_limit("myuser", max_requests=10, window_seconds=60)

        # incr should have been called with the prefixed key
        mock_pipe.incr.assert_called_once_with("test:myuser")
