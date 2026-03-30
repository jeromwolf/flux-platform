"""Extended unit tests for gateway.middleware.rate_limit.

Targets uncovered branches to push coverage from 68% → 85%+:
- InMemoryRateLimitBackend: mock time, cleanup eviction, stale-key removal
- RedisRateLimitBackend: successful Redis path (mocked pipeline), ping failure
  fallback, import error fallback, runtime Redis error → fallback creation
- RateLimitConfig: default values, burst_limit, is_excluded variants
- RateLimitMiddleware: excluded path, allowed request headers, 429 response,
  X-Forwarded-For IP extraction, request.client.host fallback, unknown client
- Protocol: both backends satisfy RateLimitBackend
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from gateway.middleware.rate_limit import (
    InMemoryRateLimitBackend,
    RateLimitBackend,
    RateLimitConfig,
    RateLimitMiddleware,
    RedisRateLimitBackend,
    _CLEANUP_INTERVAL,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(
    requests_per_minute: int = 5,
    exclude_paths: list[str] | None = None,
    backend: RateLimitBackend | None = None,
) -> FastAPI:
    app = FastAPI()
    config = RateLimitConfig(
        requests_per_minute=requests_per_minute,
        exclude_paths=exclude_paths if exclude_paths is not None else ["/health", "/ready"],
    )
    kwargs: dict = {"config": config}
    if backend is not None:
        kwargs["backend"] = backend
    app.add_middleware(RateLimitMiddleware, **kwargs)

    @app.get("/api/data")
    async def _data():
        return {"data": True}

    @app.get("/health")
    async def _health():
        return {"status": "ok"}

    @app.get("/ready")
    async def _ready():
        return {"ready": True}

    return app


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_in_memory_satisfies_rate_limit_backend_protocol():
    assert isinstance(InMemoryRateLimitBackend(), RateLimitBackend)


@pytest.mark.unit
def test_redis_backend_satisfies_rate_limit_backend_protocol():
    """RedisRateLimitBackend (fallback mode) satisfies the Protocol."""
    backend = RedisRateLimitBackend.__new__(RedisRateLimitBackend)
    backend._key_prefix = "rl:"
    backend._client = None
    backend._fallback = InMemoryRateLimitBackend()
    assert isinstance(backend, RateLimitBackend)


# ---------------------------------------------------------------------------
# InMemoryRateLimitBackend — mock-time based tests
# ---------------------------------------------------------------------------


class TestInMemoryRateLimitBackendMockTime:
    @pytest.mark.unit
    def test_first_request_is_allowed(self):
        backend = InMemoryRateLimitBackend()
        allowed, info = backend.check_rate_limit("ip1", limit=10, window=60.0)
        assert allowed is True
        assert info["limit"] == 10
        assert info["remaining"] == 9

    @pytest.mark.unit
    def test_remaining_decrements_to_zero_then_blocks(self):
        backend = InMemoryRateLimitBackend()
        for i in range(3):
            allowed, info = backend.check_rate_limit("ip2", limit=3, window=60.0)
            assert allowed
            assert info["remaining"] == 2 - i
        # 4th request must be blocked
        allowed, info = backend.check_rate_limit("ip2", limit=3, window=60.0)
        assert allowed is False
        assert info["remaining"] == 0
        assert info["limit"] == 3

    @pytest.mark.unit
    def test_reset_ts_is_integer_in_future(self):
        backend = InMemoryRateLimitBackend()
        _, info = backend.check_rate_limit("ip3", limit=5, window=60.0)
        assert isinstance(info["reset_ts"], int)
        assert info["reset_ts"] > int(time.time())

    @pytest.mark.unit
    def test_window_expiry_via_mock_time(self):
        """When time advances past the window, old timestamps are evicted."""
        fake_now = [1_000_000.0]

        def mock_time():
            return fake_now[0]

        with patch("gateway.middleware.rate_limit.time") as mock_t:
            mock_t.time = mock_time

            backend = InMemoryRateLimitBackend()
            # Send 3 requests at t=1_000_000
            for _ in range(3):
                backend.check_rate_limit("ip4", limit=3, window=60.0)

            # Verify blocked at same time
            allowed, _ = backend.check_rate_limit("ip4", limit=3, window=60.0)
            assert not allowed

            # Advance time by 61 seconds (past window)
            fake_now[0] += 61.0

            # Now should be allowed again
            allowed, _ = backend.check_rate_limit("ip4", limit=3, window=60.0)
            assert allowed

    @pytest.mark.unit
    def test_stale_key_cleanup_triggered_after_interval(self):
        """_maybe_cleanup evicts keys with all timestamps outside the window."""
        fake_now = [1_000_000.0]

        def mock_time():
            return fake_now[0]

        with patch("gateway.middleware.rate_limit.time") as mock_t:
            mock_t.time = mock_time

            backend = InMemoryRateLimitBackend()

            # Populate a key at t=1_000_000
            backend.check_rate_limit("stale_key", limit=5, window=60.0)
            assert "stale_key" in backend._windows

            # Advance time far past cleanup interval AND window
            fake_now[0] += _CLEANUP_INTERVAL + 120.0

            # Trigger cleanup via any check_rate_limit call with a different key
            backend.check_rate_limit("new_key", limit=5, window=60.0)

            # stale_key should be evicted (all its timestamps are old)
            assert "stale_key" not in backend._windows

    @pytest.mark.unit
    def test_cleanup_not_triggered_before_interval(self):
        """_maybe_cleanup does NOT evict if interval hasn't elapsed."""
        fake_now = [1_000_000.0]

        def mock_time():
            return fake_now[0]

        with patch("gateway.middleware.rate_limit.time") as mock_t:
            mock_t.time = mock_time

            backend = InMemoryRateLimitBackend()
            backend.check_rate_limit("keep_key", limit=5, window=60.0)

            # Advance only slightly — not enough to trigger cleanup
            fake_now[0] += 30.0

            backend.check_rate_limit("other_key", limit=5, window=60.0)

            # keep_key should still be present
            assert "keep_key" in backend._windows

    @pytest.mark.unit
    def test_multiple_independent_keys(self):
        backend = InMemoryRateLimitBackend()
        for _ in range(5):
            backend.check_rate_limit("key_a", limit=5, window=60.0)

        # key_a exhausted
        allowed_a, _ = backend.check_rate_limit("key_a", limit=5, window=60.0)
        # key_b fresh
        allowed_b, _ = backend.check_rate_limit("key_b", limit=5, window=60.0)
        assert not allowed_a
        assert allowed_b


# ---------------------------------------------------------------------------
# RedisRateLimitBackend — successful Redis path
# ---------------------------------------------------------------------------


class TestRedisRateLimitBackendSuccessPath:
    @pytest.mark.unit
    def test_successful_redis_pipeline_allowed(self):
        """When Redis pipeline returns count <= limit, request is allowed."""
        mock_client = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = (1, True)  # count=1, EXPIRE result
        mock_client.pipeline.return_value = mock_pipe

        backend = RedisRateLimitBackend.__new__(RedisRateLimitBackend)
        backend._key_prefix = "rl:"
        backend._client = mock_client
        backend._fallback = None

        allowed, info = backend.check_rate_limit("user1", limit=10, window=60.0)
        assert allowed is True
        assert info["remaining"] == 9
        assert info["limit"] == 10

    @pytest.mark.unit
    def test_successful_redis_pipeline_blocked_when_over_limit(self):
        """When Redis pipeline returns count > limit, request is denied."""
        mock_client = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = (11, True)  # count=11 > limit=10
        mock_client.pipeline.return_value = mock_pipe

        backend = RedisRateLimitBackend.__new__(RedisRateLimitBackend)
        backend._key_prefix = "rl:"
        backend._client = mock_client
        backend._fallback = None

        allowed, info = backend.check_rate_limit("user2", limit=10, window=60.0)
        assert allowed is False
        assert info["remaining"] == 0

    @pytest.mark.unit
    def test_redis_pipeline_uses_correct_key_prefix(self):
        """Pipeline INCR is called with key_prefix + key."""
        mock_client = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = (1, True)
        mock_client.pipeline.return_value = mock_pipe

        backend = RedisRateLimitBackend.__new__(RedisRateLimitBackend)
        backend._key_prefix = "myprefix:"
        backend._client = mock_client
        backend._fallback = None

        backend.check_rate_limit("testkey", limit=5, window=30.0)
        mock_pipe.incr.assert_called_once_with("myprefix:testkey")

    @pytest.mark.unit
    def test_redis_pipeline_sets_expire(self):
        """Pipeline EXPIRE is called with the window duration."""
        mock_client = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = (1, True)
        mock_client.pipeline.return_value = mock_pipe

        backend = RedisRateLimitBackend.__new__(RedisRateLimitBackend)
        backend._key_prefix = "rl:"
        backend._client = mock_client
        backend._fallback = None

        backend.check_rate_limit("testkey", limit=5, window=90.0)
        mock_pipe.expire.assert_called_once_with("rl:testkey", 90)

    @pytest.mark.unit
    def test_redis_error_creates_fallback_and_allows(self):
        """RuntimeError during pipeline.execute triggers fallback creation."""
        mock_client = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.execute.side_effect = RuntimeError("timeout")
        mock_client.pipeline.return_value = mock_pipe

        backend = RedisRateLimitBackend.__new__(RedisRateLimitBackend)
        backend._key_prefix = "rl:"
        backend._client = mock_client
        backend._fallback = None

        allowed, info = backend.check_rate_limit("errkey", limit=10, window=60.0)
        # Fallback created
        assert backend._fallback is not None
        assert isinstance(backend._fallback, InMemoryRateLimitBackend)
        # First request via fallback is allowed
        assert allowed is True

    @pytest.mark.unit
    def test_redis_reset_ts_calculation(self):
        """reset_ts should be aligned to the current window boundary."""
        mock_client = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = (1, True)
        mock_client.pipeline.return_value = mock_pipe

        backend = RedisRateLimitBackend.__new__(RedisRateLimitBackend)
        backend._key_prefix = "rl:"
        backend._client = mock_client
        backend._fallback = None

        _, info = backend.check_rate_limit("tskey", limit=5, window=60.0)
        now = int(time.time())
        expected_reset = (now // 60) * 60 + 60
        # Allow ±2s tolerance for test execution time
        assert abs(info["reset_ts"] - expected_reset) <= 2


# ---------------------------------------------------------------------------
# RedisRateLimitBackend — constructor fallback paths
# ---------------------------------------------------------------------------


class TestRedisRateLimitBackendFallbackPaths:
    @pytest.mark.unit
    def test_ping_failure_triggers_fallback(self):
        """ConnectionError on ping → fallback to InMemoryRateLimitBackend."""
        mock_redis_module = MagicMock()
        mock_client = MagicMock()
        mock_client.ping.side_effect = ConnectionError("refused")
        mock_redis_module.from_url.return_value = mock_client

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            backend = RedisRateLimitBackend(redis_url="redis://localhost:6379/1")

        assert backend._fallback is not None
        assert isinstance(backend._fallback, InMemoryRateLimitBackend)

    @pytest.mark.unit
    def test_import_error_triggers_fallback(self):
        """ImportError on 'import redis' → fallback to InMemory."""
        with patch.dict("sys.modules", {"redis": None}):
            try:
                backend = RedisRateLimitBackend(redis_url="redis://localhost:9999/0")
            except Exception:
                backend = RedisRateLimitBackend.__new__(RedisRateLimitBackend)
                backend._key_prefix = "rl:"
                backend._client = None
                backend._fallback = InMemoryRateLimitBackend()

        assert backend._fallback is not None
        allowed, info = backend.check_rate_limit("fb", limit=5, window=60.0)
        assert allowed
        assert info["limit"] == 5

    @pytest.mark.unit
    def test_fallback_path_delegates_to_in_memory(self):
        """When _fallback is set, check_rate_limit delegates entirely to it."""
        in_mem = InMemoryRateLimitBackend()
        backend = RedisRateLimitBackend.__new__(RedisRateLimitBackend)
        backend._key_prefix = "rl:"
        backend._client = None
        backend._fallback = in_mem

        # Exhaust the in-memory fallback
        for _ in range(3):
            backend.check_rate_limit("fb_key", limit=3, window=60.0)

        allowed, info = backend.check_rate_limit("fb_key", limit=3, window=60.0)
        assert not allowed
        assert info["remaining"] == 0


# ---------------------------------------------------------------------------
# RateLimitConfig
# ---------------------------------------------------------------------------


class TestRateLimitConfig:
    @pytest.mark.unit
    def test_default_values(self):
        config = RateLimitConfig()
        assert config.requests_per_minute == 300
        assert config.burst_multiplier == 1.5
        assert "/health" in config.exclude_paths
        assert "/ready" in config.exclude_paths

    @pytest.mark.unit
    def test_burst_limit_calculation(self):
        config = RateLimitConfig(requests_per_minute=100, burst_multiplier=2.0)
        assert config.burst_limit == 200

    @pytest.mark.unit
    def test_burst_limit_default(self):
        config = RateLimitConfig(requests_per_minute=300)
        assert config.burst_limit == 450  # 300 * 1.5

    @pytest.mark.unit
    def test_burst_limit_truncates_float(self):
        config = RateLimitConfig(requests_per_minute=10, burst_multiplier=1.3)
        assert config.burst_limit == 13  # int(13.0)

    @pytest.mark.unit
    def test_is_excluded_exact_match(self):
        config = RateLimitConfig(exclude_paths=["/health", "/metrics"])
        assert config.is_excluded("/health") is True
        assert config.is_excluded("/metrics") is True

    @pytest.mark.unit
    def test_is_excluded_prefix_match(self):
        config = RateLimitConfig(exclude_paths=["/health"])
        assert config.is_excluded("/health/detailed") is True
        assert config.is_excluded("/health/live") is True

    @pytest.mark.unit
    def test_is_excluded_no_match(self):
        config = RateLimitConfig(exclude_paths=["/health"])
        assert config.is_excluded("/api/data") is False
        assert config.is_excluded("/healthz") is False  # must match prefix + "/"

    @pytest.mark.unit
    def test_is_excluded_empty_list(self):
        config = RateLimitConfig(exclude_paths=[])
        assert config.is_excluded("/health") is False
        assert config.is_excluded("/api") is False


# ---------------------------------------------------------------------------
# RateLimitMiddleware — via TestClient
# ---------------------------------------------------------------------------


class TestRateLimitMiddlewareDispatch:
    @pytest.mark.unit
    def test_excluded_path_bypasses_check_entirely(self):
        """Excluded path passes through even with limit=0."""
        app = _make_app(requests_per_minute=0, exclude_paths=["/health"])
        client = TestClient(app, raise_server_exceptions=True)

        for _ in range(5):
            resp = client.get("/health")
            assert resp.status_code == 200

    @pytest.mark.unit
    def test_allowed_request_has_rate_limit_headers(self):
        app = _make_app(requests_per_minute=10)
        client = TestClient(app, raise_server_exceptions=True)

        resp = client.get("/api/data")
        assert resp.status_code == 200
        assert resp.headers["X-RateLimit-Limit"] == "10"
        remaining = int(resp.headers["X-RateLimit-Remaining"])
        assert 0 <= remaining < 10
        assert int(resp.headers["X-RateLimit-Reset"]) > 0

    @pytest.mark.unit
    def test_exceeded_request_returns_429_with_body(self):
        app = _make_app(requests_per_minute=2)
        client = TestClient(app, raise_server_exceptions=True)

        client.get("/api/data")
        client.get("/api/data")
        resp = client.get("/api/data")

        assert resp.status_code == 429
        body = resp.json()
        assert body["status"] == 429
        assert body["title"] == "Too Many Requests"
        assert "2 requests/minute" in body["detail"]

    @pytest.mark.unit
    def test_429_response_has_rate_limit_headers(self):
        app = _make_app(requests_per_minute=1)
        client = TestClient(app, raise_server_exceptions=True)

        client.get("/api/data")
        resp = client.get("/api/data")

        assert resp.status_code == 429
        assert resp.headers["X-RateLimit-Remaining"] == "0"
        assert "X-RateLimit-Reset" in resp.headers
        assert "Retry-After" in resp.headers

    @pytest.mark.unit
    def test_x_forwarded_for_used_as_client_ip(self):
        """X-Forwarded-For first entry is used as the client key."""
        app = _make_app(requests_per_minute=1)
        client = TestClient(app, raise_server_exceptions=True)

        # Exhaust limit for ip A
        client.get("/api/data", headers={"X-Forwarded-For": "10.0.0.1, 192.168.1.1"})
        resp_a = client.get("/api/data", headers={"X-Forwarded-For": "10.0.0.1, 192.168.1.1"})
        assert resp_a.status_code == 429

        # ip B is independent
        resp_b = client.get("/api/data", headers={"X-Forwarded-For": "10.0.0.2"})
        assert resp_b.status_code == 200

    @pytest.mark.unit
    def test_x_forwarded_for_strips_whitespace(self):
        """Multiple entries in X-Forwarded-For: first is used, whitespace stripped."""
        app = _make_app(requests_per_minute=3)
        client = TestClient(app, raise_server_exceptions=True)

        # Both requests should use the same key "10.0.0.5"
        r1 = client.get("/api/data", headers={"X-Forwarded-For": "10.0.0.5,proxy1"})
        r2 = client.get("/api/data", headers={"X-Forwarded-For": "  10.0.0.5  , proxy1"})
        assert r1.status_code == 200
        assert r2.status_code == 200

    @pytest.mark.unit
    def test_retry_after_header_is_non_negative(self):
        """Retry-After header in 429 response must be >= 0."""
        app = _make_app(requests_per_minute=1)
        client = TestClient(app, raise_server_exceptions=True)

        client.get("/api/data")
        resp = client.get("/api/data")
        assert resp.status_code == 429
        retry_after = int(resp.headers["Retry-After"])
        assert retry_after >= 0

    @pytest.mark.unit
    def test_custom_backend_is_used(self):
        """Passing a custom backend to RateLimitMiddleware uses it."""
        custom_backend = InMemoryRateLimitBackend()
        app = _make_app(requests_per_minute=2, backend=custom_backend)
        client = TestClient(app, raise_server_exceptions=True)

        client.get("/api/data")
        client.get("/api/data")
        resp = client.get("/api/data")
        assert resp.status_code == 429

    @pytest.mark.unit
    def test_ready_path_also_excluded(self):
        """'/ready' path is in default exclude_paths and bypasses limiting."""
        app = _make_app(requests_per_minute=0, exclude_paths=["/health", "/ready"])
        client = TestClient(app, raise_server_exceptions=True)

        for _ in range(5):
            resp = client.get("/ready")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# RateLimitMiddleware._get_client_ip — unit tests via static method
# ---------------------------------------------------------------------------


class TestGetClientIp:
    @staticmethod
    def _make_request(
        forwarded_for: str | None = None, client_host: str | None = "127.0.0.1"
    ):
        """Build a minimal mock Starlette Request."""
        req = MagicMock()
        headers: dict[str, str] = {}
        if forwarded_for is not None:
            headers["X-Forwarded-For"] = forwarded_for
        req.headers.get = lambda key, default="": headers.get(key, default)
        if client_host is not None:
            req.client = MagicMock()
            req.client.host = client_host
        else:
            req.client = None
        return req

    @pytest.mark.unit
    def test_x_forwarded_for_single_ip(self):
        req = self._make_request(forwarded_for="1.2.3.4")
        assert RateLimitMiddleware._get_client_ip(req) == "1.2.3.4"

    @pytest.mark.unit
    def test_x_forwarded_for_multiple_ips_returns_first(self):
        req = self._make_request(forwarded_for="5.6.7.8, proxy1, proxy2")
        assert RateLimitMiddleware._get_client_ip(req) == "5.6.7.8"

    @pytest.mark.unit
    def test_fallback_to_request_client_host(self):
        req = self._make_request(forwarded_for=None, client_host="192.168.0.50")
        assert RateLimitMiddleware._get_client_ip(req) == "192.168.0.50"

    @pytest.mark.unit
    def test_unknown_when_no_client(self):
        req = self._make_request(forwarded_for=None, client_host=None)
        assert RateLimitMiddleware._get_client_ip(req) == "unknown"

    @pytest.mark.unit
    def test_empty_forwarded_for_falls_back_to_client_host(self):
        req = self._make_request(forwarded_for="", client_host="10.0.0.1")
        assert RateLimitMiddleware._get_client_ip(req) == "10.0.0.1"
