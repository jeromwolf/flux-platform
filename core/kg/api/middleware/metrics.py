"""Prometheus-compatible metrics for the Maritime KG API.

Provides request counting, duration histograms, and a /metrics endpoint.
Uses a lightweight built-in implementation with no external dependencies.

Usage::

    from kg.api.middleware.metrics import MetricsMiddleware, metrics_endpoint
    app.add_middleware(MetricsMiddleware)
    app.add_route("/metrics", metrics_endpoint)
"""

from __future__ import annotations

import re
import threading
import time
from collections import defaultdict
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response


class _MetricsStore:
    """Thread-safe metrics storage."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._request_count: dict[str, int] = defaultdict(int)
        self._request_duration_sum: dict[str, float] = defaultdict(float)
        self._request_duration_count: dict[str, int] = defaultdict(int)
        self._error_count: dict[str, int] = defaultdict(int)
        self._active_requests: int = 0

    def record_request(self, method: str, path: str, status: int, duration: float) -> None:
        """Record a completed request."""
        key = f'{method}|{path}|{status}'
        with self._lock:
            self._request_count[key] += 1
            self._request_duration_sum[key] += duration
            self._request_duration_count[key] += 1
            if status >= 400:
                error_key = f'{method}|{path}|{status // 100}xx'
                self._error_count[error_key] += 1

    def increment_active(self) -> None:
        with self._lock:
            self._active_requests += 1

    def decrement_active(self) -> None:
        with self._lock:
            self._active_requests -= 1

    def format_prometheus(self) -> str:
        """Format metrics in Prometheus text exposition format."""
        lines: list[str] = []

        lines.append("# HELP http_requests_total Total number of HTTP requests")
        lines.append("# TYPE http_requests_total counter")
        with self._lock:
            for key, count in sorted(self._request_count.items()):
                method, path, status = key.split("|")
                lines.append(
                    f'http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}'
                )

        lines.append("")
        lines.append("# HELP http_request_duration_seconds HTTP request duration in seconds")
        lines.append("# TYPE http_request_duration_seconds summary")
        with self._lock:
            for key, total in sorted(self._request_duration_sum.items()):
                method, path, status = key.split("|")
                count = self._request_duration_count[key]
                lines.append(
                    f'http_request_duration_seconds_sum{{method="{method}",path="{path}",status="{status}"}} {total:.6f}'
                )
                lines.append(
                    f'http_request_duration_seconds_count{{method="{method}",path="{path}",status="{status}"}} {count}'
                )

        lines.append("")
        lines.append("# HELP http_requests_active Current active requests")
        lines.append("# TYPE http_requests_active gauge")
        with self._lock:
            lines.append(f"http_requests_active {self._active_requests}")

        lines.append("")
        lines.append("# HELP http_errors_total Total HTTP errors by class")
        lines.append("# TYPE http_errors_total counter")
        with self._lock:
            for key, count in sorted(self._error_count.items()):
                method, path, error_class = key.split("|")
                lines.append(
                    f'http_errors_total{{method="{method}",path="{path}",error_class="{error_class}"}} {count}'
                )

        lines.append("")
        return "\n".join(lines)


# Global metrics store singleton
_store = _MetricsStore()


def get_metrics_store() -> _MetricsStore:
    """Return the global metrics store."""
    return _store


def reset_metrics() -> None:
    """Reset all metrics (for testing)."""
    global _store
    _store = _MetricsStore()


class MetricsMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that records request metrics."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Normalize path to avoid high cardinality
        path = self._normalize_path(request.url.path)

        if path == "/metrics":
            return await call_next(request)

        _store.increment_active()
        start = time.monotonic()
        try:
            response = await call_next(request)
            duration = time.monotonic() - start
            _store.record_request(request.method, path, response.status_code, duration)
            return response
        except Exception:
            duration = time.monotonic() - start
            _store.record_request(request.method, path, 500, duration)
            raise
        finally:
            _store.decrement_active()

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Normalize URL path to reduce cardinality.

        Replaces UUID-like segments and numeric IDs with placeholders.
        """
        # Replace UUIDs
        path = re.sub(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '{id}',
            path,
        )
        # Replace numeric-only path segments
        path = re.sub(r'/\d+(?=/|$)', '/{id}', path)
        return path


async def metrics_endpoint(request: Request) -> PlainTextResponse:
    """Prometheus metrics endpoint handler."""
    return PlainTextResponse(
        content=_store.format_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
