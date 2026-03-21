"""RFC 7807 Problem Details models for IMSP API error responses.

Defines Pydantic models for standardized error responses and
the ``IMSPHTTPException`` for raising structured errors in route handlers.

See: https://datatracker.ietf.org/doc/html/rfc7807
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Individual error detail within a Problem Details response."""

    field: str | None = None
    code: str = ""
    message: str = ""


class ProblemDetail(BaseModel):
    """RFC 7807 Problem Details response model.

    Used as the standard error response format for all IMSP API errors.
    """

    type: str = "about:blank"
    title: str = ""
    status: int = 500
    detail: str = ""
    instance: str = ""
    timestamp: str = ""
    traceId: str = ""
    errors: list[ErrorDetail] = Field(default_factory=list)


@dataclass(frozen=True)
class ErrorCodeInfo:
    """Metadata for a registered error code."""

    code: str  # e.g. "AUTH-1001"
    http_status: int  # e.g. 401
    title: str  # e.g. "Token Expired"
    severity: str  # FATAL / ERROR / WARN / INFO


class IMSPHTTPException(Exception):
    """Structured HTTP exception for IMSP API.

    Raised in route handlers to produce RFC 7807 error responses.

    Args:
        error_code: IMSP error code (e.g. "KG-2001").
        status: HTTP status code.
        detail: Human-readable error description.
        context: Additional context key-value pairs.
    """

    def __init__(
        self,
        error_code: str,
        *,
        status: int = 500,
        detail: str = "",
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.error_code = error_code
        self.status = status
        self.detail = detail
        self.context = context or {}
