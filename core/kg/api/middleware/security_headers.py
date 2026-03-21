"""Security headers middleware (OWASP recommended).

Adds standard security headers to all HTTP responses to protect against
common web vulnerabilities. Configurable via environment variables.

Headers applied:
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 0 (modern browsers use CSP instead)
- Referrer-Policy: strict-origin-when-cross-origin
- Content-Security-Policy: default-src 'self'
- Strict-Transport-Security (HSTS, production only)
- Permissions-Policy: restrict sensitive APIs
- Cache-Control: no-store for API responses

Usage::

    from kg.api.middleware.security_headers import SecurityHeadersMiddleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Or with custom config
    app.add_middleware(SecurityHeadersMiddleware, enable_hsts=True)
"""
from __future__ import annotations

import os
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add OWASP-recommended security headers to all responses.

    Args:
        app: The ASGI application.
        enable_hsts: Enable Strict-Transport-Security header. Defaults to
            True in production (ENV != "development").
        hsts_max_age: HSTS max-age in seconds (default 1 year = 31536000).
        csp_policy: Custom Content-Security-Policy directive. Defaults to
            "default-src 'self'" which is appropriate for API-only services.
    """

    def __init__(
        self,
        app: Any,
        enable_hsts: bool | None = None,
        hsts_max_age: int = 31_536_000,
        csp_policy: str = "default-src 'self'",
    ) -> None:
        super().__init__(app)
        # Auto-detect HSTS from environment if not explicitly set
        if enable_hsts is None:
            self._enable_hsts = os.environ.get("ENV", "development") != "development"
        else:
            self._enable_hsts = enable_hsts
        self._hsts_max_age = hsts_max_age
        self._csp_policy = csp_policy

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Add security headers to the response."""
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Disable legacy XSS filter (CSP is the modern replacement)
        response.headers["X-XSS-Protection"] = "0"

        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content Security Policy
        response.headers["Content-Security-Policy"] = self._csp_policy

        # Restrict browser feature access
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), "
            "payment=(), usb=(), magnetometer=()"
        )

        # HSTS — only in production/staging
        if self._enable_hsts:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self._hsts_max_age}; includeSubDomains"
            )

        # Prevent caching of API responses (not for static assets)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"

        return response
