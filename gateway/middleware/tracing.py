"""Distributed tracing middleware for Gateway — W3C Traceparent + Zipkin export."""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from urllib.request import Request, urlopen

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

logger = logging.getLogger(__name__)

ZIPKIN_ENDPOINT = os.environ.get("ZIPKIN_ENDPOINT", "")


def _generate_trace_id() -> str:
    """Generate a 32-char hex trace ID (128-bit)."""
    return uuid.uuid4().hex


def _generate_span_id() -> str:
    """Generate a 16-char hex span ID (64-bit)."""
    return uuid.uuid4().hex[:16]


class GatewayTracingMiddleware(BaseHTTPMiddleware):
    """Propagates W3C traceparent header and reports spans to Zipkin.

    Parses an incoming ``traceparent`` header if present (W3C Trace Context
    spec, version ``00``), or creates a new root trace when none is provided.
    A fresh span ID is generated for each gateway request.  On response, the
    outbound ``traceparent`` header is set and — when ``ZIPKIN_ENDPOINT`` is
    configured — the span is reported via a best-effort fire-and-forget POST.
    """

    async def dispatch(self, request: StarletteRequest, call_next) -> Response:
        # Parse or generate trace context
        traceparent = request.headers.get("traceparent", "")
        if traceparent and traceparent.startswith("00-"):
            parts = traceparent.split("-")
            trace_id = parts[1] if len(parts) > 1 else _generate_trace_id()
            parent_span_id = parts[2] if len(parts) > 2 else None
        else:
            trace_id = _generate_trace_id()
            parent_span_id = None

        span_id = _generate_span_id()
        new_traceparent = f"00-{trace_id}-{span_id}-01"

        request.state.trace_id = trace_id
        request.state.span_id = span_id

        start_time = time.time()
        response = await call_next(request)
        duration_us = int((time.time() - start_time) * 1_000_000)

        response.headers["traceparent"] = new_traceparent

        # Report to Zipkin if configured
        if ZIPKIN_ENDPOINT:
            _report_span(
                trace_id=trace_id,
                span_id=span_id,
                parent_id=parent_span_id,
                name=f"{request.method} {request.url.path}",
                duration_us=duration_us,
                status_code=response.status_code,
            )

        return response


def _report_span(
    trace_id: str,
    span_id: str,
    parent_id: str | None,
    name: str,
    duration_us: int,
    status_code: int,
) -> None:
    """Send span to Zipkin (fire-and-forget, non-blocking via best effort).

    Args:
        trace_id: 32-char hex trace identifier.
        span_id: 16-char hex span identifier.
        parent_id: Parent span ID, or ``None`` for root spans.
        name: Human-readable span name (e.g. ``GET /api/health``).
        duration_us: Span duration in microseconds.
        status_code: HTTP response status code attached as a tag.
    """
    try:
        span: dict = {
            "traceId": trace_id,
            "id": span_id,
            "name": name,
            "timestamp": int(time.time() * 1_000_000) - duration_us,
            "duration": duration_us,
            "localEndpoint": {"serviceName": "imsp-gateway"},
            "tags": {"http.status_code": str(status_code)},
        }
        if parent_id:
            span["parentId"] = parent_id

        data = json.dumps([span]).encode()
        req = Request(
            ZIPKIN_ENDPOINT,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urlopen(req, timeout=1)
    except Exception:  # noqa: S110
        pass  # Fire-and-forget — never surface tracing errors to callers
