"""Audit logging middleware for state-changing API operations.

Captures structured audit trail entries for POST, PUT, PATCH, and DELETE
requests. Logs are written via Python's logging module so they integrate
with the existing JSON logging infrastructure.

Only state-changing methods are audited to keep the log volume manageable.
GET and OPTIONS requests are silently passed through.

Usage is automatic when registered as middleware::

    from kg.api.middleware.audit import AuditMiddleware
    app.add_middleware(AuditMiddleware)
"""
from __future__ import annotations

import logging
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Dedicated audit logger — allows separate log routing via logging config
audit_logger = logging.getLogger("kg.audit")

# HTTP methods that represent state changes
_AUDITED_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Paths to exclude from audit logging (health, metrics, docs)
_EXCLUDED_PREFIXES = ("/api/v1/health", "/metrics", "/docs", "/openapi.json", "/redoc")


class AuditMiddleware(BaseHTTPMiddleware):
    """Log structured audit entries for state-changing HTTP operations.

    Captures:
    - Timestamp (ISO 8601)
    - HTTP method and path
    - Client IP
    - User identity (from request.state if available)
    - Request ID (from RequestIdMiddleware)
    - Response status code
    - Duration in milliseconds
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Process request and emit audit log if state-changing."""
        if request.method not in _AUDITED_METHODS:
            return await call_next(request)

        # Skip non-business paths
        if any(request.url.path.startswith(p) for p in _EXCLUDED_PREFIXES):
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 2)

        # Build audit entry
        entry = _build_audit_entry(request, response, duration_ms)

        # Log at INFO level for successful mutations, WARNING for errors
        if response.status_code < 400:
            audit_logger.info(
                "AUDIT: %s %s → %d",
                request.method,
                request.url.path,
                response.status_code,
                extra=entry,
            )
        else:
            audit_logger.warning(
                "AUDIT: %s %s → %d",
                request.method,
                request.url.path,
                response.status_code,
                extra=entry,
            )

        return response


def _build_audit_entry(
    request: Request,
    response: Response,
    duration_ms: float,
) -> dict[str, Any]:
    """Build structured audit log entry from request/response."""
    # Extract user identity if available (from auth middleware)
    user_id = ""
    if hasattr(request.state, "user_id"):
        user_id = request.state.user_id
    elif hasattr(request.state, "api_key"):
        # Mask API key for security
        key = request.state.api_key
        user_id = f"apikey:***{key[-4:]}" if len(key) > 4 else "apikey:***"

    # Extract request ID from RequestIdMiddleware
    request_id = getattr(request.state, "request_id", "")

    # Extract trace context if available
    trace_id = ""
    if hasattr(request.state, "trace_context"):
        trace_id = request.state.trace_context.trace_id

    # Client IP (respects X-Forwarded-For)
    client_ip = _get_client_ip(request)

    return {
        "audit_action": request.method,
        "audit_path": request.url.path,
        "audit_query": str(request.query_params) if request.query_params else "",
        "audit_user": user_id,
        "audit_client_ip": client_ip,
        "audit_status": response.status_code,
        "audit_duration_ms": duration_ms,
        "audit_request_id": request_id,
        "audit_trace_id": trace_id,
    }


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting reverse proxy headers."""
    # X-Forwarded-For: client, proxy1, proxy2
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    # X-Real-IP (nginx)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    # Direct connection
    if request.client:
        return request.client.host
    return ""
