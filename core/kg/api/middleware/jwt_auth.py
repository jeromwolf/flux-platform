"""JWT Bearer token authentication.

Supports HS256 symmetric signing for development/PoC.
Designed to be extended to RS256 + JWKS for Keycloak OIDC in 2nd year.

Environment Variables:
    JWT_SECRET_KEY: Symmetric signing key (HS256). Required in production.
    JWT_ALGORITHM: Algorithm (default: HS256).
    JWT_ISSUER: Expected token issuer (optional).
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from kg.api.deps import get_app_config
from kg.config import AppConfig

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class JWTPayload:
    """Decoded JWT token payload."""

    sub: str  # Subject (user ID)
    role: str  # User role
    exp: int  # Expiration timestamp
    iss: str = ""  # Issuer
    iat: int = 0  # Issued at
    extra: dict[str, Any] = field(default_factory=dict)


def _decode_jwt(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Uses PyJWT for signature-verified decoding.

    Args:
        token: The raw JWT token string.

    Returns:
        Decoded payload dictionary.

    Raises:
        ValueError: If the token is invalid, expired, or cannot be verified.
    """
    try:
        import jwt as pyjwt
    except ImportError:
        raise ImportError(
            "PyJWT is required for JWT authentication. "
            "Install it with: pip install PyJWT"
        )

    secret = os.getenv("JWT_SECRET_KEY", "")
    if not secret:
        raise ValueError(
            "JWT_SECRET_KEY environment variable is required. "
            "Set it to a secure random string."
        )
    algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    issuer = os.getenv("JWT_ISSUER")

    options: dict[str, Any] = {}
    if not issuer:
        options["verify_iss"] = False

    try:
        payload = pyjwt.decode(
            token,
            secret,
            algorithms=[algorithm],
            issuer=issuer,
            options=options,
        )
        return payload
    except pyjwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except pyjwt.InvalidTokenError as e:
        raise ValueError(f"Invalid token: {e}")


def create_token(
    sub: str,
    role: str = "user",
    expires_in: int = 3600,
    extra: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT token (utility for testing and development).

    Args:
        sub: Subject (user ID).
        role: User role.
        expires_in: Token lifetime in seconds (default: 1 hour).
        extra: Additional claims to include.

    Returns:
        Signed JWT token string.

    Raises:
        ImportError: If PyJWT is not installed.
    """
    import jwt as pyjwt

    secret = os.getenv("JWT_SECRET_KEY", "")
    if not secret:
        raise ValueError(
            "JWT_SECRET_KEY environment variable is required for token creation."
        )
    algorithm = os.getenv("JWT_ALGORITHM", "HS256")

    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": sub,
        "role": role,
        "iat": now,
        "exp": now + expires_in,
        **(extra or {}),
    }

    issuer = os.getenv("JWT_ISSUER")
    if issuer:
        payload["iss"] = issuer

    return pyjwt.encode(payload, secret, algorithm=algorithm)


def get_jwt_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    config: AppConfig = Depends(get_app_config),
) -> JWTPayload | None:
    """Extract and validate JWT from Authorization: Bearer header.

    In development mode, returns None (auth skipped).
    If no Bearer token is present, returns None (falls through to API Key auth).

    Args:
        credentials: Bearer token from Authorization header.
        config: Application configuration.

    Returns:
        JWTPayload if valid token, None if no token or dev mode.

    Raises:
        HTTPException: 401 if token is present but invalid/expired.
    """
    # Skip in development mode
    if config.env == "development":
        return None

    if credentials is None:
        return None  # No Bearer token -- fall through to API Key auth

    try:
        payload = _decode_jwt(credentials.credentials)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    return JWTPayload(
        sub=payload.get("sub", ""),
        role=payload.get("role", "user"),
        exp=payload.get("exp", 0),
        iss=payload.get("iss", ""),
        iat=payload.get("iat", 0),
    )
