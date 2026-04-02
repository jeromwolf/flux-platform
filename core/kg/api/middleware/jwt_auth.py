"""JWT Bearer token authentication — Dual Mode (HS256 + RS256/JWKS).

Supports two authentication modes:

1. **RS256 / Keycloak OIDC mode** (activated when ``KEYCLOAK_URL`` is set):
   - Fetches public keys from Keycloak JWKS endpoint.
   - Verifies token signature with RS256.
   - Extracts Keycloak ``realm_access.roles`` into :class:`JWTPayload`.
   - Caches JWKS with a configurable TTL (default 3600 s).
   - Falls back to HS256 if JWKS fetch fails.

2. **HS256 / symmetric mode** (legacy, ``KEYCLOAK_URL`` not set):
   - Uses ``JWT_SECRET_KEY`` for HMAC-SHA256 verification.
   - Fully backward-compatible with all existing callers.

Environment Variables:
    JWT_SECRET_KEY: Symmetric signing key (HS256). Required in HS256 mode.
    JWT_ALGORITHM: Algorithm override (default: HS256). Only used in HS256 mode.
    JWT_ISSUER: Expected token issuer (optional, HS256 mode).
    KEYCLOAK_URL: Keycloak base URL, e.g. ``http://keycloak:8080``.
                  When set, RS256+JWKS mode is activated.
    KEYCLOAK_REALM: Keycloak realm name (default: ``imsp``).
    KEYCLOAK_CLIENT_ID: Keycloak client ID (default: ``imsp-api``).
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from kg.api.deps import get_app_config
from kg.config import AppConfig

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)

# JWKS 캐시 TTL (초)
_JWKS_CACHE_TTL = 3600

# 모듈-레벨 JWKS 캐시 — 프로세스 전체에서 공유
_jwks_cache: dict[str, Any] | None = None
_jwks_cached_at: float = 0.0


@dataclass(frozen=True)
class JWTPayload:
    """Decoded JWT token payload."""

    sub: str  # Subject (user ID)
    role: str  # User role
    exp: int  # Expiration timestamp
    iss: str = ""  # Issuer
    iat: int = 0  # Issued at
    roles: list[str] = field(default_factory=list)  # Keycloak realm_access.roles
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# JWKS helpers
# ---------------------------------------------------------------------------


def _jwks_uri() -> str:
    """Build the Keycloak JWKS URI from environment variables."""
    keycloak_url = os.getenv("KEYCLOAK_URL", "").rstrip("/")
    realm = os.getenv("KEYCLOAK_REALM", "imsp")
    return f"{keycloak_url}/realms/{realm}/protocol/openid-connect/certs"


def _fetch_jwks() -> dict[str, Any] | None:
    """Fetch JWKS from Keycloak, with module-level TTL cache.

    Returns:
        Parsed JWKS dict on success, ``None`` on failure.
    """
    global _jwks_cache, _jwks_cached_at  # noqa: PLW0603

    now = time.time()
    if _jwks_cache is not None and (now - _jwks_cached_at) < _JWKS_CACHE_TTL:
        return _jwks_cache

    uri = _jwks_uri()
    try:
        req = urllib.request.Request(uri)
        with urllib.request.urlopen(req, timeout=5) as resp:
            jwks: dict[str, Any] = json.loads(resp.read())
        _jwks_cache = jwks
        _jwks_cached_at = now
        logger.info("JWKS fetched from %s (%d keys)", uri, len(jwks.get("keys", [])))
        return jwks
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to fetch JWKS from %s: %s", uri, exc)
        return None


def _get_signing_key(token: str, jwks: dict[str, Any]) -> Any:
    """Extract the RS256 public key matching the token's ``kid``.

    Args:
        token: Raw JWT string.
        jwks: Parsed JWKS dict from Keycloak.

    Returns:
        Public key object (for PyJWT), or ``None`` if not found.
    """
    import jwt as pyjwt  # PyJWT

    try:
        header = pyjwt.get_unverified_header(token)
        kid = header.get("kid")

        for key_data in jwks.get("keys", []):
            if key_data.get("kid") == kid:
                from jwt.algorithms import RSAAlgorithm

                return RSAAlgorithm.from_jwk(key_data)

        logger.warning("No matching JWKS key found for kid=%s", kid)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to extract signing key: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Core decode logic
# ---------------------------------------------------------------------------


def _decode_jwt_rs256(token: str) -> dict[str, Any]:
    """Decode and verify a JWT using RS256 + JWKS.

    Args:
        token: Raw JWT string.

    Returns:
        Decoded payload dictionary.

    Raises:
        ValueError: If the token is invalid, expired, or cannot be verified.
    """
    import jwt as pyjwt

    keycloak_url = os.getenv("KEYCLOAK_URL", "").rstrip("/")
    realm = os.getenv("KEYCLOAK_REALM", "imsp")
    client_id = os.getenv("KEYCLOAK_CLIENT_ID", "imsp-api")
    issuer = f"{keycloak_url}/realms/{realm}"

    jwks = _fetch_jwks()
    if jwks is None:
        raise ValueError("JWKS fetch failed")

    signing_key = _get_signing_key(token, jwks)
    if signing_key is None:
        raise ValueError("No matching JWKS key found for token")

    try:
        payload = pyjwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=issuer,
            options={
                "verify_aud": False,  # Keycloak uses azp, not aud
            },
        )
        logger.debug("RS256 JWT verified via JWKS for sub=%s", payload.get("sub"))
        return payload
    except pyjwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except pyjwt.InvalidTokenError as e:
        raise ValueError(f"Invalid token: {e}")


def _decode_jwt_hs256(token: str) -> dict[str, Any]:
    """Decode and verify a JWT using HS256 (symmetric).

    Args:
        token: Raw JWT string.

    Returns:
        Decoded payload dictionary.

    Raises:
        ValueError: If the token is invalid, expired, or cannot be verified.
    """
    import jwt as pyjwt

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


def _decode_jwt(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token — dual-mode dispatcher.

    Chooses between RS256+JWKS (Keycloak) and HS256 (symmetric) based on
    whether ``KEYCLOAK_URL`` is set in the environment.

    * When ``KEYCLOAK_URL`` is set → tries RS256+JWKS first; if JWKS fetch
      fails, logs a warning and falls back to HS256.
    * When ``KEYCLOAK_URL`` is not set → uses HS256 exclusively.

    Args:
        token: The raw JWT token string.

    Returns:
        Decoded payload dictionary.

    Raises:
        ImportError: If PyJWT is not installed.
        ValueError: If the token is invalid, expired, or cannot be verified.
    """
    try:
        import jwt as _pyjwt  # noqa: F401  (just to check availability)
    except ImportError:
        raise ImportError(
            "PyJWT is required for JWT authentication. "
            "Install it with: pip install PyJWT"
        )

    keycloak_url = os.getenv("KEYCLOAK_URL", "")

    if keycloak_url:
        # RS256 / Keycloak 모드
        try:
            return _decode_jwt_rs256(token)
        except ValueError as exc:
            # JWKS 페치 실패 시 HS256으로 폴백
            if "JWKS fetch failed" in str(exc) or "No matching JWKS key" in str(exc):
                logger.warning(
                    "RS256 decode failed (%s) — falling back to HS256", exc
                )
                return _decode_jwt_hs256(token)
            # 그 외 (만료, 서명 불일치 등)는 그대로 올림
            raise

    # HS256 / 대칭 모드 (기존 동작 유지)
    return _decode_jwt_hs256(token)


# ---------------------------------------------------------------------------
# Token creation (dev/testing helper — HS256 only)
# ---------------------------------------------------------------------------


def create_token(
    sub: str,
    role: str = "user",
    expires_in: int = 3600,
    extra: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT token (utility for testing and development).

    Always uses HS256 regardless of whether ``KEYCLOAK_URL`` is set.
    This function is intentionally limited to development / test contexts.

    Args:
        sub: Subject (user ID).
        role: User role.
        expires_in: Token lifetime in seconds (default: 1 hour).
        extra: Additional claims to include.

    Returns:
        Signed JWT token string.

    Raises:
        ImportError: If PyJWT is not installed.
        ValueError: If ``JWT_SECRET_KEY`` is not set.
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


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


def get_jwt_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    config: AppConfig = Depends(get_app_config),
) -> JWTPayload | None:
    """Extract and validate JWT from Authorization: Bearer header.

    In development mode, returns None (auth skipped).
    If no Bearer token is present, returns None (falls through to API Key auth).

    Extracts ``realm_access.roles`` from Keycloak tokens when present.

    Args:
        credentials: Bearer token from Authorization header.
        config: Application configuration.

    Returns:
        JWTPayload if valid token, None if no token or dev mode.

    Raises:
        HTTPException: 401 if token is present but invalid/expired.
    """
    # 개발 모드에서는 JWT 검증 건너뜀
    if config.env == "development":
        logger.warning(
            "SECURITY WARNING: JWT validation bypassed in development mode. "
            "Set ENV=production to enforce JWT authentication."
        )
        return None

    if credentials is None:
        return None  # Bearer 토큰 없음 → API Key 인증으로 폴스루

    try:
        payload = _decode_jwt(credentials.credentials)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Keycloak realm_access.roles 추출
    realm_access = payload.get("realm_access", {})
    roles: list[str] = realm_access.get("roles", []) if isinstance(realm_access, dict) else []

    return JWTPayload(
        sub=payload.get("sub", ""),
        role=payload.get("role", "user"),
        exp=payload.get("exp", 0),
        iss=payload.get("iss", ""),
        iat=payload.get("iat", 0),
        roles=roles,
    )
