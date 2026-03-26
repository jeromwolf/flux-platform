"""Token bucket + sliding-window rate limiter middleware.

Provides per-user rate limiting based on JWT role.  Storage is pluggable:

- :class:`InMemoryRateLimitBackend` — token-bucket, single-process (default)
- :class:`RedisRateLimitBackend`    — INCR/EXPIRE fixed-window, distributed

The Redis backend is selected automatically by :func:`~kg.api.app.create_app`
when a Redis connection is available.  In-memory is used as a fallback so the
service degrades gracefully rather than failing.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Role -> requests per minute
ROLE_LIMITS: dict[str, int] = {
    "admin": 600,
    "researcher": 300,
    "operator": 300,
    "data_provider": 200,
    "viewer": 100,
    "user": 100,
}

DEFAULT_LIMIT = 100  # requests per minute for unknown roles

# Redis key namespace
_REDIS_KEY_PREFIX = "imsp:rl:"


# ---------------------------------------------------------------------------
# Token bucket (kept for backward-compat and in-memory backend)
# ---------------------------------------------------------------------------


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""

    capacity: int
    refill_rate: float  # tokens per second
    tokens: float = field(init=False)
    last_refill: float = field(init=False)
    _lock: threading.Lock = field(init=False, default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        self.tokens = float(self.capacity)
        self.last_refill = time.monotonic()

    def consume(self) -> bool:
        """Try to consume one token. Returns True if allowed."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False

    @property
    def remaining(self) -> int:
        """Current remaining tokens (approximate)."""
        return max(0, int(self.tokens))


# ---------------------------------------------------------------------------
# Backend Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class RateLimitBackend(Protocol):
    """Protocol for rate limit state storage.

    Implementations must be thread-safe and return a 2-tuple
    ``(allowed, headers)`` where *headers* is a plain ``dict[str, str]``
    containing the following keys (when non-empty):

    - ``X-RateLimit-Limit``    — configured maximum per window
    - ``X-RateLimit-Remaining``— requests remaining after this one
    - ``X-RateLimit-Reset``    — seconds until (or Unix TS of) window reset
    """

    def check_limit(
        self, key: str, max_requests: int, window_seconds: int
    ) -> tuple[bool, dict[str, str]]:
        """Check whether *key* is within its rate limit.

        Args:
            key: Client identifier (user sub or IP address).
            max_requests: Maximum requests allowed in *window_seconds*.
            window_seconds: Window duration in seconds.

        Returns:
            ``(allowed, headers)`` — *allowed* is ``False`` when exceeded.
        """
        ...


# ---------------------------------------------------------------------------
# In-Memory Backend (token bucket)
# ---------------------------------------------------------------------------


class InMemoryRateLimitBackend:
    """In-memory token-bucket rate limiter (single-process).

    Wraps :class:`TokenBucket` instances keyed by client identity.
    Thread-safe via per-bucket locks inside :class:`TokenBucket`.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, TokenBucket] = {}
        self._buckets_lock = threading.Lock()

    def _get_bucket(self, key: str, max_requests: int, window_seconds: int) -> TokenBucket:
        with self._buckets_lock:
            if key not in self._buckets:
                self._buckets[key] = TokenBucket(
                    capacity=max_requests,
                    refill_rate=max_requests / float(window_seconds),
                )
            return self._buckets[key]

    def check_limit(
        self, key: str, max_requests: int, window_seconds: int
    ) -> tuple[bool, dict[str, str]]:
        """Check and record a request using the token-bucket algorithm.

        Args:
            key: Client identifier.
            max_requests: Bucket capacity (= requests per window).
            window_seconds: Window duration used to compute refill rate.

        Returns:
            ``(allowed, headers)`` tuple.
        """
        bucket = self._get_bucket(key, max_requests, window_seconds)
        allowed = bucket.consume()
        reset_seconds = int(window_seconds - (time.monotonic() - bucket.last_refill) % window_seconds)
        headers: dict[str, str] = {
            "X-RateLimit-Limit": str(max_requests),
            "X-RateLimit-Remaining": str(bucket.remaining),
            "X-RateLimit-Reset": str(reset_seconds),
        }
        return allowed, headers


# ---------------------------------------------------------------------------
# Redis Backend (INCR/EXPIRE fixed-window)
# ---------------------------------------------------------------------------


class RedisRateLimitBackend:
    """Redis-backed fixed-window rate limiter.

    Uses ``INCR`` + ``EXPIRE`` in a pipeline for an atomic counter per
    ``(key, window)`` slot.  Falls back to the in-memory backend on any
    Redis error so the service remains available (fail-open).

    Args:
        redis_client: A connected ``redis.Redis`` (or compatible) client.
        key_prefix: Namespace prefix for Redis keys.
    """

    def __init__(
        self,
        redis_client: Any,
        key_prefix: str = _REDIS_KEY_PREFIX,
    ) -> None:
        self._client = redis_client
        self._prefix = key_prefix
        self._fallback: InMemoryRateLimitBackend | None = None

    def check_limit(
        self, key: str, max_requests: int, window_seconds: int
    ) -> tuple[bool, dict[str, str]]:
        """Check and record a request using Redis INCR/EXPIRE.

        Falls back to in-memory backend on any Redis error (fail-open).

        Args:
            key: Client identifier.
            max_requests: Maximum requests allowed in *window_seconds*.
            window_seconds: Window duration in seconds.

        Returns:
            ``(allowed, headers)`` tuple.
        """
        redis_key = f"{self._prefix}{key}"
        try:
            pipe = self._client.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, window_seconds)
            results = pipe.execute()
            current = int(results[0])
            allowed = current <= max_requests
            remaining = max(0, max_requests - current)
            headers: dict[str, str] = {
                "X-RateLimit-Limit": str(max_requests),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(window_seconds),
            }
            return allowed, headers
        except Exception as exc:
            logger.warning(
                "Redis error in check_limit (%s) — falling back to in-memory", exc
            )
            if self._fallback is None:
                self._fallback = InMemoryRateLimitBackend()
            return self._fallback.check_limit(key, max_requests, window_seconds)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-user rate limiting middleware.

    Extracts user identity from request state (set by auth middleware)
    or falls back to client IP address.  Rate limits are role-based.

    Skips rate limiting for health and metrics endpoints.

    Args:
        app: The next ASGI application.
        default_limit: Requests per minute for unknown roles.
        backend: Storage backend.  Defaults to :class:`InMemoryRateLimitBackend`.
    """

    _SKIP_PATHS = frozenset({"/api/v1/health", "/metrics"})
    _WINDOW_SECONDS = 60

    def __init__(
        self,
        app: Any,
        default_limit: int = DEFAULT_LIMIT,
        backend: RateLimitBackend | None = None,
    ) -> None:
        super().__init__(app)
        self._default_limit = default_limit
        self._backend: RateLimitBackend = backend or InMemoryRateLimitBackend()

    async def dispatch(self, request: Request, call_next: Any) -> Response:  # type: ignore[override]
        """Process request through rate limiter."""
        path = request.url.path

        # Skip rate limiting for health/metrics endpoints
        if path in self._SKIP_PATHS:
            return await call_next(request)

        # Extract identity and role
        user_info = getattr(request.state, "user", None)
        if user_info and isinstance(user_info, dict):
            identity = user_info.get("sub", "")
            role = user_info.get("role", "user")
        else:
            identity = request.client.host if request.client else "unknown"
            role = "user"

        limit = ROLE_LIMITS.get(role, self._default_limit)

        allowed, headers = self._backend.check_limit(
            key=identity,
            max_requests=limit,
            window_seconds=self._WINDOW_SECONDS,
        )

        if not allowed:
            reset_seconds = int(headers.get("X-RateLimit-Reset", str(self._WINDOW_SECONDS)))
            logger.warning("Rate limit exceeded for %s (role=%s)", identity, role)
            return JSONResponse(
                status_code=429,
                content={
                    "type": "https://imsp.kriso.re.kr/errors/API-5002",
                    "title": "Rate Limit Exceeded",
                    "status": 429,
                    "detail": f"Rate limit of {limit}/min exceeded. Retry after {reset_seconds}s.",
                },
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_seconds),
                    "Retry-After": str(reset_seconds),
                },
            )

        response = await call_next(request)

        # Add rate limit headers to successful responses
        response.headers["X-RateLimit-Limit"] = headers.get("X-RateLimit-Limit", str(limit))
        response.headers["X-RateLimit-Remaining"] = headers.get("X-RateLimit-Remaining", "0")
        response.headers["X-RateLimit-Reset"] = headers.get(
            "X-RateLimit-Reset", str(self._WINDOW_SECONDS)
        )

        return response
