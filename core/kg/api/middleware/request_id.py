"""Request ID middleware.

Generates a unique ``X-Request-ID`` header for each request if not
already present. The ID is available via ``request.state.request_id``
for use in logging and error responses.
"""
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Ensure every request has a unique X-Request-ID."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        """Attach or propagate X-Request-ID for the request lifecycle."""
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
