"""Structured JSON access logging middleware."""
from __future__ import annotations

import json
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("gateway.access")


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Logs every request in structured JSON format for log aggregation."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()

        # Capture request info
        request_id = getattr(request.state, "request_id", "-")
        trace_id = getattr(request.state, "trace_id", "-")
        user_id = getattr(request.state, "user_id", "anonymous")

        response = await call_next(request)

        duration_ms = (time.time() - start_time) * 1000

        status = response.status_code
        if status < 400:
            level = "INFO"
        elif status < 500:
            level = "WARN"
        else:
            level = "ERROR"

        log_entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "level": level,
            "method": request.method,
            "path": request.url.path,
            "query": str(request.query_params) if request.query_params else None,
            "status": status,
            "duration_ms": round(duration_ms, 2),
            "user_id": user_id,
            "request_id": request_id,
            "trace_id": trace_id,
            "user_agent": request.headers.get("user-agent", "-"),
            "remote_addr": request.client.host if request.client else "-",
        }

        # Remove None values for cleaner JSON
        log_entry = {k: v for k, v in log_entry.items() if v is not None}

        logger.info(json.dumps(log_entry, ensure_ascii=False))

        return response
