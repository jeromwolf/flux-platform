"""API key authentication middleware and dependency.

In development mode (``config.env == "development"``), authentication is
skipped entirely.  In production, every request must carry a valid
``X-API-Key`` header whose value matches the ``APP_API_KEY`` environment
variable.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from kg.api.deps import get_app_config
from kg.api.middleware.jwt_auth import JWTPayload, get_jwt_payload
from kg.config import AppConfig

logger = logging.getLogger(__name__)

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_current_api_key(
    api_key: Optional[str] = Security(_API_KEY_HEADER),  # noqa: B008, UP045
    config: AppConfig = Depends(get_app_config),  # noqa: B008
) -> Optional[str]:  # noqa: UP045
    """Validate the API key from the request header.

    Args:
        api_key: Value of the ``X-API-Key`` header (injected by FastAPI).
        config: Application configuration (injected by FastAPI).

    Returns:
        The validated API key string, or ``None`` in development mode.

    Raises:
        HTTPException: 401 if the key is missing or invalid in production.
        HTTPException: 500 if ``APP_API_KEY`` is not configured in production.
    """
    # Skip auth in development mode
    if config.env == "development":
        return None

    expected_key = os.getenv("APP_API_KEY", "")
    if not expected_key:
        logger.warning(
            "APP_API_KEY not configured in production mode -- rejecting request"
        )
        raise HTTPException(
            status_code=500,
            detail="Server misconfiguration: API key not set",
        )

    if not api_key or api_key != expected_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
        )

    return api_key


def get_current_user(
    jwt_payload: JWTPayload | None = Depends(get_jwt_payload),
    api_key: str | None = Depends(get_current_api_key),
    config: AppConfig = Depends(get_app_config),
) -> dict[str, Any]:
    """Unified authentication: tries JWT first, then API Key.

    In development mode, returns a default dev user.

    Args:
        jwt_payload: Decoded JWT payload (injected by FastAPI).
        api_key: Validated API key (injected by FastAPI).
        config: Application configuration (injected by FastAPI).

    Returns:
        Dict with user info: ``{"sub": str, "role": str, "auth_method": str}``

    Raises:
        HTTPException: 401 if neither JWT nor API key is valid in production.
    """
    if config.env == "development":
        return {"sub": "dev-user", "role": "admin", "auth_method": "dev-bypass"}

    if jwt_payload is not None:
        return {
            "sub": jwt_payload.sub,
            "role": jwt_payload.role,
            "auth_method": "jwt",
        }

    if api_key is not None:
        return {
            "sub": "api-key-user",
            "role": "admin",
            "auth_method": "api-key",
        }

    raise HTTPException(
        status_code=401,
        detail="Authentication required: provide JWT Bearer token or X-API-Key",
    )
