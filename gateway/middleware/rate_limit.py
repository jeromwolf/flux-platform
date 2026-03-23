"""Sliding-window rate-limit middleware.

Y1: In-memory storage per-process.
Y2: Redis backend for distributed rate limiting.

Backend selection:
    - Default: InMemoryRateLimitBackend (no dependencies)
    - Optional: RedisRateLimitBackend (requires ``redis`` package)
      Falls back to InMemoryRateLimitBackend if redis is unavailable.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# 자동 정리 주기 (초)
_CLEANUP_INTERVAL = 60.0


# ---------------------------------------------------------------------------
# Backend Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class RateLimitBackend(Protocol):
    """Protocol for rate-limit storage backends.

    Implementations must be thread-safe (or async-safe) and return a 2-tuple:
        (allowed: bool, info: dict)

    The ``info`` dict MUST contain:
        - ``limit`` (int): configured maximum per window
        - ``remaining`` (int): requests remaining after this one
        - ``reset_ts`` (int): Unix timestamp when the window resets
    """

    def check_rate_limit(
        self,
        key: str,
        limit: int,
        window: float,
    ) -> tuple[bool, dict[str, int]]:
        """Check and record a request for *key*.

        Args:
            key: Client identifier (e.g. IP address).
            limit: Maximum requests allowed within *window* seconds.
            window: Sliding window duration in seconds.

        Returns:
            ``(allowed, info)`` where *allowed* is False when limit exceeded.
        """
        ...


# ---------------------------------------------------------------------------
# In-Memory Backend
# ---------------------------------------------------------------------------


class InMemoryRateLimitBackend:
    """Sliding-window in-memory rate-limit backend.

    Stores per-key request timestamps in a plain dict guarded by a
    :class:`threading.Lock`.  Stale entries are evicted periodically.
    """

    def __init__(self) -> None:
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()
        self._last_cleanup = time.time()

    def check_rate_limit(
        self,
        key: str,
        limit: int,
        window: float = 60.0,
    ) -> tuple[bool, dict[str, int]]:
        """Check and record a request for *key*.

        Args:
            key: Client identifier.
            limit: Maximum requests per window.
            window: Sliding window in seconds.

        Returns:
            ``(allowed, info)`` tuple.
        """
        now = time.time()
        window_start = now - window

        with self._lock:
            self._maybe_cleanup(now, window)

            timestamps = self._windows[key]
            timestamps[:] = [t for t in timestamps if t > window_start]

            reset_ts = int(window_start + window) + 1

            if len(timestamps) >= limit:
                return False, {
                    "limit": limit,
                    "remaining": 0,
                    "reset_ts": reset_ts,
                }

            timestamps.append(now)
            remaining = max(0, limit - len(timestamps))
            return True, {
                "limit": limit,
                "remaining": remaining,
                "reset_ts": reset_ts,
            }

    def _maybe_cleanup(self, now: float, window: float) -> None:
        """Evict expired client windows if the cleanup interval has elapsed.

        Must be called while holding ``self._lock``.

        Args:
            now: Current epoch timestamp in seconds.
            window: Sliding window size in seconds.
        """
        if now - self._last_cleanup < _CLEANUP_INTERVAL:
            return

        window_start = now - window
        stale_keys = [
            k
            for k, timestamps in self._windows.items()
            if not any(t > window_start for t in timestamps)
        ]
        for k in stale_keys:
            del self._windows[k]

        self._last_cleanup = now
        if stale_keys:
            logger.debug("Rate-limit cleanup: evicted %d stale entries", len(stale_keys))


# ---------------------------------------------------------------------------
# Redis Backend
# ---------------------------------------------------------------------------


class RedisRateLimitBackend:
    """Redis-backed sliding-window rate-limit backend.

    Uses the INCR + EXPIRE atomic pattern for approximate fixed-window
    counting.  If the ``redis`` package is unavailable or the connection
    fails at construction time, falls back to :class:`InMemoryRateLimitBackend`.

    Args:
        redis_url: Redis connection URL (default ``redis://localhost:6379/0``).
        key_prefix: Namespace prefix for Redis keys.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        key_prefix: str = "rl:",
    ) -> None:
        self._key_prefix = key_prefix
        self._fallback: InMemoryRateLimitBackend | None = None
        self._client: Any = None

        try:
            import redis  # type: ignore[import]

            self._client = redis.from_url(redis_url, decode_responses=True)
            # Eagerly test connectivity
            self._client.ping()
            logger.info("RedisRateLimitBackend connected to %s", redis_url)
        except Exception as exc:
            logger.warning(
                "Redis unavailable (%s) — falling back to InMemoryRateLimitBackend",
                exc,
            )
            self._fallback = InMemoryRateLimitBackend()

    def check_rate_limit(
        self,
        key: str,
        limit: int,
        window: float = 60.0,
    ) -> tuple[bool, dict[str, int]]:
        """Check and record a request for *key* using Redis INCR/EXPIRE.

        Falls back to in-memory backend on any Redis error.

        Args:
            key: Client identifier.
            limit: Maximum requests per window.
            window: Window duration in seconds.

        Returns:
            ``(allowed, info)`` tuple.
        """
        if self._fallback is not None:
            return self._fallback.check_rate_limit(key, limit, window)

        redis_key = f"{self._key_prefix}{key}"
        window_int = int(window)
        now = int(time.time())
        reset_ts = (now // window_int) * window_int + window_int

        try:
            pipe = self._client.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, window_int)
            count, _ = pipe.execute()

            count = int(count)
            allowed = count <= limit
            remaining = max(0, limit - count)
            return allowed, {
                "limit": limit,
                "remaining": remaining,
                "reset_ts": reset_ts,
            }
        except Exception as exc:
            logger.warning("Redis error in check_rate_limit (%s) — falling back", exc)
            if self._fallback is None:
                self._fallback = InMemoryRateLimitBackend()
            return self._fallback.check_rate_limit(key, limit, window)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class RateLimitConfig:
    """Rate-limit configuration.

    Attributes:
        requests_per_minute: Maximum allowed requests per client per 60-second window.
        burst_multiplier: Multiplier applied to requests_per_minute for burst capacity.
        exclude_paths: Paths that bypass rate limiting entirely.
    """

    requests_per_minute: int = 300
    burst_multiplier: float = 1.5
    exclude_paths: list[str] = field(default_factory=lambda: ["/health", "/ready"])

    @property
    def burst_limit(self) -> int:
        """Maximum burst capacity (requests_per_minute * burst_multiplier)."""
        return int(self.requests_per_minute * self.burst_multiplier)

    def is_excluded(self, path: str) -> bool:
        """Check whether a path is excluded from rate limiting.

        Args:
            path: URL path to check.

        Returns:
            True if the path matches an exclusion prefix.
        """
        for excluded in self.exclude_paths:
            if path == excluded or path.startswith(excluded + "/"):
                return True
        return False


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate-limit middleware.

    Tracks per-client request timestamps within a rolling 60-second window.
    Returns HTTP 429 (RFC 7807 format) when the client exceeds the configured
    limit.  Thread-safe via the chosen backend.

    Headers added to every non-excluded response:
        - ``X-RateLimit-Limit``: configured requests_per_minute
        - ``X-RateLimit-Remaining``: requests remaining in current window
        - ``X-RateLimit-Reset``: Unix timestamp when the window resets

    Args:
        app: The next ASGI application.
        config: Rate-limit configuration. Defaults to :class:`RateLimitConfig`.
        backend: Storage backend. Defaults to :class:`InMemoryRateLimitBackend`.
    """

    def __init__(
        self,
        app: Any,
        config: RateLimitConfig | None = None,
        backend: RateLimitBackend | None = None,
    ) -> None:
        super().__init__(app)
        self._config = config or RateLimitConfig()
        self._backend: RateLimitBackend = backend or InMemoryRateLimitBackend()

    # ------------------------------------------------------------------
    # Middleware dispatch
    # ------------------------------------------------------------------

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        """Process the incoming request through the rate-limit check.

        Args:
            request: The incoming Starlette request.
            call_next: Callable to forward the request downstream.

        Returns:
            A :class:`JSONResponse` with status 429 if the limit is exceeded,
            otherwise the downstream response with rate-limit headers attached.
        """
        path = request.url.path

        # 제외 경로는 바로 통과
        if self._config.is_excluded(path):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        limit = self._config.requests_per_minute

        allowed, info = self._backend.check_rate_limit(
            key=client_ip,
            limit=limit,
            window=60.0,
        )

        reset_ts = info["reset_ts"]
        remaining_after = info["remaining"]

        if not allowed:
            now = int(time.time())
            logger.warning(
                "Rate limit exceeded: client=%s path=%s limit=%d",
                client_ip,
                path,
                limit,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "type": "about:blank",
                    "title": "Too Many Requests",
                    "status": 429,
                    "detail": (
                        f"Rate limit of {limit} requests/minute exceeded. "
                        f"Try again after {reset_ts}."
                    ),
                },
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_ts),
                    "Retry-After": str(max(0, reset_ts - now)),
                },
            )

        response = await call_next(request)

        # 응답 헤더에 rate-limit 정보 추가
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining_after)
        response.headers["X-RateLimit-Reset"] = str(reset_ts)
        return response

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Resolve the real client IP from headers or connection info.

        Prefers ``X-Forwarded-For`` (first entry) when present, falls back
        to ``request.client.host``.

        Args:
            request: Incoming Starlette request.

        Returns:
            Client IP address string.
        """
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"
