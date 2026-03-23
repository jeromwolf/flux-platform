"""Sliding-window rate-limit middleware.

Y1: In-memory storage per-process.
Y2: Migrate to Redis for distributed rate limiting.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# 자동 정리 주기 (초)
_CLEANUP_INTERVAL = 60.0


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


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate-limit middleware.

    Tracks per-client request timestamps within a rolling 60-second window.
    Returns HTTP 429 (RFC 7807 format) when the client exceeds the configured
    limit.  Thread-safe via :class:`threading.Lock`.

    Headers added to every non-excluded response:
        - ``X-RateLimit-Limit``: configured requests_per_minute
        - ``X-RateLimit-Remaining``: requests remaining in current window
        - ``X-RateLimit-Reset``: Unix timestamp when the window resets

    Args:
        app: The next ASGI application.
        config: Rate-limit configuration. Defaults to :class:`RateLimitConfig`.
    """

    def __init__(self, app: Any, config: RateLimitConfig | None = None) -> None:
        super().__init__(app)
        self._config = config or RateLimitConfig()
        # client_ip -> list of request timestamps (float epoch seconds)
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()
        self._last_cleanup = time.time()

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
        now = time.time()
        window_start = now - 60.0

        with self._lock:
            self._maybe_cleanup(now)

            timestamps = self._windows[client_ip]
            # 윈도우 밖 타임스탬프 제거
            timestamps[:] = [t for t in timestamps if t > window_start]

            limit = self._config.requests_per_minute
            remaining = max(0, limit - len(timestamps))
            reset_ts = int(window_start + 60.0) + 1  # 다음 윈도우 시작

            if len(timestamps) >= limit:
                logger.warning(
                    "Rate limit exceeded: client=%s path=%s count=%d limit=%d",
                    client_ip,
                    path,
                    len(timestamps),
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
                        "Retry-After": str(reset_ts - int(now)),
                    },
                )

            # 현재 요청 기록
            timestamps.append(now)
            remaining_after = max(0, limit - len(timestamps))

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

    def _maybe_cleanup(self, now: float) -> None:
        """Evict expired client windows if the cleanup interval has elapsed.

        Must be called while holding ``self._lock``.

        Args:
            now: Current epoch timestamp in seconds.
        """
        if now - self._last_cleanup < _CLEANUP_INTERVAL:
            return

        window_start = now - 60.0
        stale_keys = [
            key
            for key, timestamps in self._windows.items()
            if not any(t > window_start for t in timestamps)
        ]
        for key in stale_keys:
            del self._windows[key]

        self._last_cleanup = now
        if stale_keys:
            logger.debug("Rate-limit cleanup: evicted %d stale entries", len(stale_keys))
