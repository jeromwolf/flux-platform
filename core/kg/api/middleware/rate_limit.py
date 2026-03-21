"""Token bucket rate limiter middleware.

Provides per-user rate limiting based on JWT role. Uses in-memory
token buckets for Y1; Redis-backed implementation planned for Y2.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

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


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-user rate limiting middleware using token buckets.

    Extracts user identity from request state (set by auth middleware)
    or falls back to client IP address. Rate limits are role-based.

    Skips rate limiting for health and metrics endpoints.
    """

    def __init__(self, app, default_limit: int = DEFAULT_LIMIT) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._buckets: dict[str, TokenBucket] = {}
        self._buckets_lock = threading.Lock()
        self._default_limit = default_limit

    def _get_bucket(self, key: str, limit: int) -> TokenBucket:
        """Get or create a token bucket for the given key."""
        with self._buckets_lock:
            if key not in self._buckets:
                self._buckets[key] = TokenBucket(
                    capacity=limit,
                    refill_rate=limit / 60.0,  # refill per second
                )
            return self._buckets[key]

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        """Process request through rate limiter."""
        path = request.url.path

        # Skip rate limiting for health/metrics endpoints
        if path in ("/api/v1/health", "/metrics"):
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
        bucket = self._get_bucket(identity, limit)

        if not bucket.consume():
            # Rate limit exceeded
            logger.warning("Rate limit exceeded for %s (role=%s)", identity, role)
            reset_seconds = int(60 - (time.monotonic() - bucket.last_refill) % 60)
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

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(bucket.remaining)

        return response
