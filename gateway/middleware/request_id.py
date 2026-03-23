"""Request ID tracking middleware.

모든 요청/응답에 X-Request-ID 헤더를 부착한다.
클라이언트가 X-Request-ID 를 보내면 그 값을 재사용하고,
없으면 uuid4 hex 를 새로 생성한다.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)

_REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every HTTP request and response.

    If the incoming request already carries ``X-Request-ID``, that value is
    preserved and echoed back in the response.  Otherwise a new ``uuid4``
    hex string is generated.  The ID is also stored on ``request.state.request_id``
    for downstream handlers and other middleware to access.

    The request ID appears in structured log records emitted by this middleware,
    making distributed tracing straightforward even before a full tracing backend
    (e.g. Zipkin) is wired in.

    Args:
        app: The next ASGI application.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        """Inject a request ID and log the incoming request.

        Args:
            request: The incoming Starlette request.
            call_next: Callable that forwards the request to the next layer.

        Returns:
            The downstream response with ``X-Request-ID`` header attached.
        """
        # 클라이언트 제공 ID 우선, 없으면 신규 생성
        request_id = request.headers.get(_REQUEST_ID_HEADER) or uuid4().hex

        # request.state 에 저장 — 다운스트림 핸들러에서 접근 가능
        request.state.request_id = request_id

        logger.debug(
            "Incoming request: method=%s path=%s request_id=%s",
            request.method,
            request.url.path,
            request_id,
        )

        response = await call_next(request)

        # 응답 헤더에 부착
        response.headers[_REQUEST_ID_HEADER] = request_id
        return response
