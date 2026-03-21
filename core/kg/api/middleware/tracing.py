"""Distributed tracing middleware (W3C Traceparent compatible).

Propagates trace context (trace_id, span_id, parent_span_id) through
the request lifecycle. Integrates with structured JSON logging and
the existing RequestIdMiddleware.

Supports incoming W3C Traceparent headers::

    traceparent: 00-{trace_id}-{span_id}-{flags}

When no traceparent header is present, generates new trace/span IDs.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


@dataclass(frozen=True)
class TraceContext:
    """Immutable trace context for a single request span."""
    trace_id: str          # 32-char hex (128-bit)
    span_id: str           # 16-char hex (64-bit)
    parent_span_id: str    # 16-char hex or "" if root span
    sampled: bool          # Whether this trace is sampled

    def to_traceparent(self) -> str:
        """Format as W3C Traceparent header value."""
        flags = "01" if self.sampled else "00"
        return f"00-{self.trace_id}-{self.span_id}-{flags}"

    @classmethod
    def from_traceparent(cls, header: str) -> TraceContext | None:
        """Parse W3C Traceparent header.

        Returns None if the header is malformed.
        Format: {version}-{trace_id}-{parent_span_id}-{flags}
        """
        parts = header.strip().split("-")
        if len(parts) != 4:
            return None
        version, trace_id, parent_span_id, flags = parts
        if len(trace_id) != 32 or len(parent_span_id) != 16:
            return None
        try:
            int(trace_id, 16)
            int(parent_span_id, 16)
        except ValueError:
            return None
        sampled = flags[-1] == "1" if flags else False
        return cls(
            trace_id=trace_id,
            span_id=secrets.token_hex(8),  # new span for this service
            parent_span_id=parent_span_id,
            sampled=sampled,
        )

    @classmethod
    def new_root(cls, sampled: bool = True) -> TraceContext:
        """Create a new root trace context."""
        return cls(
            trace_id=secrets.token_hex(16),
            span_id=secrets.token_hex(8),
            parent_span_id="",
            sampled=sampled,
        )


def _should_sample() -> bool:
    """Determine if a new trace should be sampled.

    Uses TRACE_SAMPLE_RATE env var (0.0 to 1.0, default 1.0).
    """
    rate_str = os.environ.get("TRACE_SAMPLE_RATE", "1.0")
    try:
        rate = float(rate_str)
    except ValueError:
        rate = 1.0
    if rate >= 1.0:
        return True
    if rate <= 0.0:
        return False
    # Use the first 2 bytes of a random token as the sample decision
    return int(secrets.token_hex(2), 16) / 65535 < rate


class TracingMiddleware(BaseHTTPMiddleware):
    """Propagate W3C Traceparent trace context through requests.

    Sets request.state.trace_context with a TraceContext instance.
    Adds traceparent response header for downstream correlation.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Parse incoming traceparent or create new root
        traceparent = request.headers.get("traceparent")
        if traceparent:
            ctx = TraceContext.from_traceparent(traceparent)
            if ctx is None:
                ctx = TraceContext.new_root(sampled=_should_sample())
        else:
            ctx = TraceContext.new_root(sampled=_should_sample())

        request.state.trace_context = ctx

        response = await call_next(request)
        response.headers["traceparent"] = ctx.to_traceparent()
        return response
