"""FastAPI exception handlers for RFC 7807 Problem Details responses.

Registers handlers for:
  1. IMSPHTTPException → structured RFC 7807 response
  2. KGError hierarchy → auto-mapped RFC 7807 response
  3. RequestValidationError → API-5001 validation error
  4. HTTPException → backward-compatible RFC 7807 wrapper
  5. Unhandled Exception → SYS-9999 internal error
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException as FastAPIHTTPException
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from kg.api.error_codes import get_error_info
from kg.api.errors import ErrorDetail, IMSPHTTPException, ProblemDetail
from kg.exceptions import (
    AccessDeniedError,
    ConnectionError,
    CrawlerError,
    KGError,
    QueryError,
    SchemaError,
)

logger = logging.getLogger(__name__)

# KGError subclass → error code mapping
_KGERROR_MAP: dict[type, str] = {
    ConnectionError: "SYS-9001",
    SchemaError: "KG-2004",
    CrawlerError: "ETL-3003",
    AccessDeniedError: "AUTH-1003",
    QueryError: "KG-2001",
}


def _get_request_id(request: Request) -> str:
    """Extract or generate a request ID."""
    return getattr(request.state, "request_id", None) or request.headers.get(
        "X-Request-ID", str(uuid.uuid4())[:12]
    )


def _build_problem(
    *,
    error_code: str,
    status: int,
    detail: str,
    request: Request,
    errors: list[ErrorDetail] | None = None,
) -> ProblemDetail:
    """Build a ProblemDetail from error information."""
    info = get_error_info(error_code)
    return ProblemDetail(
        type=f"https://imsp.kriso.re.kr/errors/{error_code}",
        title=info.title if info else "Error",
        status=status,
        detail=detail,
        instance=str(request.url.path),
        timestamp=datetime.now(timezone.utc).isoformat(),
        traceId=_get_request_id(request),
        errors=errors or [],
    )


async def imsp_exception_handler(request: Request, exc: IMSPHTTPException) -> JSONResponse:
    """Handle IMSPHTTPException → RFC 7807."""
    problem = _build_problem(
        error_code=exc.error_code,
        status=exc.status,
        detail=exc.detail,
        request=request,
    )
    logger.warning("IMSP error %s: %s", exc.error_code, exc.detail)
    return JSONResponse(status_code=exc.status, content=problem.model_dump())


async def kgerror_handler(request: Request, exc: KGError) -> JSONResponse:
    """Handle KGError hierarchy → RFC 7807."""
    error_code = _KGERROR_MAP.get(type(exc), "SYS-9999")
    info = get_error_info(error_code)
    status = info.http_status if info else 500
    detail = str(exc) if str(exc) else (info.title if info else "Internal error")
    problem = _build_problem(
        error_code=error_code,
        status=status,
        detail=detail,
        request=request,
    )
    logger.error("KGError [%s]: %s", error_code, detail, exc_info=exc)
    return JSONResponse(status_code=status, content=problem.model_dump())


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors → API-5001."""
    errors = [
        ErrorDetail(
            field=".".join(str(loc) for loc in err.get("loc", [])),
            code="API-5001",
            message=err.get("msg", ""),
        )
        for err in exc.errors()
    ]
    problem = _build_problem(
        error_code="API-5001",
        status=422,
        detail=f"{len(errors)} validation error(s)",
        request=request,
        errors=errors,
    )
    return JSONResponse(status_code=422, content=problem.model_dump())


async def http_exception_handler(
    request: Request, exc: FastAPIHTTPException
) -> JSONResponse:
    """Handle FastAPI HTTPException → RFC 7807 (backward compatible).

    Preserves the ``detail`` field for existing test compatibility.
    """
    status = exc.status_code
    detail = str(exc.detail) if exc.detail else ""
    problem = _build_problem(
        error_code=f"API-{status}",
        status=status,
        detail=detail,
        request=request,
    )
    return JSONResponse(status_code=status, content=problem.model_dump())


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions → SYS-9999."""
    logger.exception("Unhandled exception: %s", exc)
    problem = _build_problem(
        error_code="SYS-9999",
        status=500,
        detail="An unexpected error occurred.",
        request=request,
    )
    return JSONResponse(status_code=500, content=problem.model_dump())


def register_error_handlers(app) -> None:
    """Register all IMSP exception handlers on a FastAPI app.

    Args:
        app: FastAPI application instance.
    """
    app.add_exception_handler(IMSPHTTPException, imsp_exception_handler)
    app.add_exception_handler(KGError, kgerror_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(FastAPIHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
