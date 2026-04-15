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

# API Key → Role mapping (admin 자동 부여 제거)
# 실제 운영에서는 DB 또는 Keycloak에서 관리
_API_KEY_ROLES: dict[str, dict] = {}


def _resolve_api_key_identity(api_key: str) -> dict:
    """API Key에 매핑된 역할을 반환. 미등록 키는 read-only."""
    if api_key in _API_KEY_ROLES:
        return _API_KEY_ROLES[api_key]
    # 미등록 API Key는 최소 권한 (read-only)
    return {
        "sub": "api-key-user",
        "role": "viewer",
        "roles": [],
        "auth_method": "api-key",
    }


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
        Dict with user info: ``{"sub": str, "role": str, "roles": list[str], "auth_method": str}``

    Raises:
        HTTPException: 401 if neither JWT nor API key is valid in production.
    """
    if config.env == "development":
        logger.critical(
            "SECURITY WARNING: Running in development mode - ALL AUTH BYPASSED. "
            "Set ENV=production for production deployments."
        )
        if os.environ.get("APP_API_KEY"):
            logger.warning(
                "APP_API_KEY is set but ENV=development. "
                "Auth is bypassed in development mode. Set ENV=production to enforce auth."
            )
        return {"sub": "dev-user", "role": "admin", "roles": [], "auth_method": "dev-bypass"}

    if jwt_payload is not None:
        return {
            "sub": jwt_payload.sub,
            "role": jwt_payload.role,
            "roles": jwt_payload.roles,
            "auth_method": "jwt",
        }

    if api_key is not None:
        return _resolve_api_key_identity(api_key)

    raise HTTPException(
        status_code=401,
        detail="Authentication required: provide JWT Bearer token or X-API-Key",
    )


def require_role(*allowed_roles: str):
    """FastAPI dependency factory that checks user roles.

    Creates a dependency that verifies the authenticated user has at least
    one of the specified roles.  In development mode, ``get_current_user``
    already returns ``role="admin"`` so all checks pass transparently.

    Usage::

        @router.post("/admin-only", dependencies=[Depends(require_role("admin"))])
        async def admin_endpoint(): ...

    Args:
        allowed_roles: One or more role names that are allowed to access
            the endpoint.

    Returns:
        A FastAPI dependency function.
    """

    async def _check_role(user: dict = Depends(get_current_user)):  # noqa: B008
        user_role = user.get("role", "")
        user_roles = user.get("roles", [])
        all_roles = {user_role} | set(user_roles)
        if not all_roles & set(allowed_roles):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required: {', '.join(allowed_roles)}",
            )
        return user

    return _check_role
