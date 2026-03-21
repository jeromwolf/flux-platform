"""Keycloak OIDC authentication bridge.

Extends the JWT authentication to support Keycloak's RS256 tokens
validated via JWKS (JSON Web Key Set) endpoints. Falls back to
HS256 when Keycloak is not configured.

Configuration via environment variables:
    KEYCLOAK_URL: Keycloak server URL (e.g., http://keycloak:8080)
    KEYCLOAK_REALM: Keycloak realm name (e.g., imsp)
    KEYCLOAK_CLIENT_ID: OIDC client ID
    KEYCLOAK_JWKS_CACHE_TTL: JWKS cache TTL in seconds (default: 3600)

When KEYCLOAK_URL is not set, this module operates in compatibility mode
using the existing HS256 JWT validation from jwt_auth.py.

Usage::

    from kg.api.middleware.keycloak import KeycloakConfig, KeycloakTokenValidator

    config = KeycloakConfig.from_env()
    validator = KeycloakTokenValidator(config)
    payload = validator.validate_token(token_string)
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KeycloakConfig:
    """Keycloak OIDC configuration.

    When ``server_url`` is empty, the system operates in compatibility
    mode using HS256 JWT validation.
    """
    server_url: str = ""
    realm: str = "imsp"
    client_id: str = "imsp-api"
    jwks_cache_ttl: int = 3600  # seconds
    # Fallback HS256 config (used when Keycloak is not configured)
    hs256_secret: str = ""
    algorithm: str = "RS256"

    @classmethod
    def from_env(cls) -> KeycloakConfig:
        """Load configuration from environment variables."""
        server_url = os.getenv("KEYCLOAK_URL", "")
        return cls(
            server_url=server_url,
            realm=os.getenv("KEYCLOAK_REALM", cls.realm),
            client_id=os.getenv("KEYCLOAK_CLIENT_ID", cls.client_id),
            jwks_cache_ttl=int(
                os.getenv("KEYCLOAK_JWKS_CACHE_TTL", str(cls.jwks_cache_ttl))
            ),
            hs256_secret=os.getenv("JWT_SECRET_KEY", ""),
            algorithm="RS256" if server_url else "HS256",
        )

    @property
    def is_keycloak_enabled(self) -> bool:
        """Whether Keycloak OIDC is configured."""
        return bool(self.server_url)

    @property
    def issuer_url(self) -> str:
        """Keycloak issuer URL for the configured realm."""
        if not self.server_url:
            return ""
        base = self.server_url.rstrip("/")
        return f"{base}/realms/{self.realm}"

    @property
    def jwks_url(self) -> str:
        """JWKS endpoint URL."""
        return f"{self.issuer_url}/protocol/openid-connect/certs"

    @property
    def token_url(self) -> str:
        """Token endpoint URL."""
        return f"{self.issuer_url}/protocol/openid-connect/token"

    @property
    def userinfo_url(self) -> str:
        """UserInfo endpoint URL."""
        return f"{self.issuer_url}/protocol/openid-connect/userinfo"

    def validate(self) -> list[str]:
        """Validate configuration. Returns list of error messages."""
        errors: list[str] = []
        if self.is_keycloak_enabled:
            if not self.realm:
                errors.append("KEYCLOAK_REALM is required when Keycloak is enabled")
            if not self.client_id:
                errors.append("KEYCLOAK_CLIENT_ID is required when Keycloak is enabled")
        else:
            if not self.hs256_secret:
                errors.append(
                    "JWT_SECRET_KEY is required in HS256 fallback mode "
                    "(set KEYCLOAK_URL for RS256)"
                )
        return errors


@dataclass(frozen=True)
class KeycloakUser:
    """Decoded Keycloak user information from token."""
    sub: str  # User ID
    username: str = ""
    email: str = ""
    realm_roles: tuple[str, ...] = ()
    client_roles: tuple[str, ...] = ()
    groups: tuple[str, ...] = ()
    name: str = ""
    given_name: str = ""
    family_name: str = ""
    extra_claims: dict[str, Any] = field(default_factory=dict)

    @property
    def primary_role(self) -> str:
        """Return the highest-priority role.

        Priority: admin > researcher > viewer > (first realm role) > user.
        """
        all_roles = set(self.realm_roles) | set(self.client_roles)
        for priority_role in ("admin", "researcher", "viewer"):
            if priority_role in all_roles:
                return priority_role
        if self.realm_roles:
            return self.realm_roles[0]
        return "user"


class JWKSKeyCache:
    """Cache for JWKS public keys with TTL-based refresh.

    Fetches public keys from the Keycloak JWKS endpoint and caches
    them for the configured TTL period.
    """

    def __init__(self, jwks_url: str, ttl: int = 3600) -> None:
        self._jwks_url = jwks_url
        self._ttl = ttl
        self._keys: dict[str, Any] = {}
        self._last_fetch: float = 0

    def get_key(self, kid: str) -> Any:
        """Get a public key by Key ID (kid).

        Args:
            kid: The Key ID from the JWT header.

        Returns:
            The public key, or None if not found.
        """
        if self._is_expired():
            self._refresh()
        return self._keys.get(kid)

    def _is_expired(self) -> bool:
        """Check if the cache has expired."""
        if not self._keys:
            return True
        return (time.monotonic() - self._last_fetch) > self._ttl

    def _refresh(self) -> None:
        """Fetch fresh keys from JWKS endpoint."""
        try:
            import urllib.request
            import json

            req = urllib.request.Request(self._jwks_url)
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            self._keys.clear()
            for key_data in data.get("keys", []):
                kid = key_data.get("kid")
                if kid:
                    self._keys[kid] = key_data
            self._last_fetch = time.monotonic()
            logger.info(
                "Refreshed JWKS keys from %s (%d keys)",
                self._jwks_url,
                len(self._keys),
            )
        except Exception as exc:
            logger.error("Failed to fetch JWKS keys: %s", exc)
            # Keep existing keys on failure
            if not self._keys:
                raise

    def clear(self) -> None:
        """Clear the key cache."""
        self._keys.clear()
        self._last_fetch = 0


class KeycloakTokenValidator:
    """Validates JWT tokens against Keycloak OIDC or HS256 fallback.

    In Keycloak mode (RS256): validates token signature against JWKS keys.
    In compatibility mode (HS256): validates using symmetric secret.

    Example::

        config = KeycloakConfig.from_env()
        validator = KeycloakTokenValidator(config)

        try:
            user = validator.validate_token(raw_token)
            print(f"Authenticated: {user.username} ({user.primary_role})")
        except ValueError as e:
            print(f"Authentication failed: {e}")
    """

    def __init__(self, config: KeycloakConfig) -> None:
        self._config = config
        self._jwks_cache: Optional[JWKSKeyCache] = None
        if config.is_keycloak_enabled:
            self._jwks_cache = JWKSKeyCache(
                config.jwks_url, config.jwks_cache_ttl
            )

    def validate_token(self, token: str) -> KeycloakUser:
        """Validate a JWT token and extract user information.

        Args:
            token: Raw JWT token string.

        Returns:
            KeycloakUser with decoded claims.

        Raises:
            ValueError: If the token is invalid, expired, or cannot be verified.
        """
        if self._config.is_keycloak_enabled:
            return self._validate_rs256(token)
        return self._validate_hs256(token)

    def _validate_rs256(self, token: str) -> KeycloakUser:
        """Validate RS256 token against Keycloak JWKS."""
        try:
            import jwt as pyjwt
        except ImportError:
            raise ImportError("PyJWT is required: pip install PyJWT[crypto]")

        try:
            # Decode header to get kid
            header = pyjwt.get_unverified_header(token)
            kid = header.get("kid")
            if not kid:
                raise ValueError("Token missing 'kid' header")

            # Get public key from cache
            assert self._jwks_cache is not None
            key_data = self._jwks_cache.get_key(kid)
            if key_data is None:
                raise ValueError(f"Unknown key ID: {kid}")

            # Construct public key from JWK
            from jwt.algorithms import RSAAlgorithm
            public_key = RSAAlgorithm.from_jwk(key_data)

            # Decode and validate
            payload = pyjwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=self._config.client_id,
                issuer=self._config.issuer_url,
            )
            return self._extract_user(payload)

        except pyjwt.ExpiredSignatureError:
            raise ValueError("Token expired")
        except pyjwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {e}")

    def _validate_hs256(self, token: str) -> KeycloakUser:
        """Validate HS256 token (compatibility mode)."""
        try:
            import jwt as pyjwt
        except ImportError:
            raise ImportError("PyJWT is required: pip install PyJWT")

        if not self._config.hs256_secret:
            raise ValueError("JWT_SECRET_KEY is required for HS256 validation")

        try:
            payload = pyjwt.decode(
                token,
                self._config.hs256_secret,
                algorithms=["HS256"],
            )
            return self._extract_user(payload)
        except pyjwt.ExpiredSignatureError:
            raise ValueError("Token expired")
        except pyjwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {e}")

    @staticmethod
    def _extract_user(payload: dict[str, Any]) -> KeycloakUser:
        """Extract KeycloakUser from decoded JWT payload.

        Handles both Keycloak-style and simple JWT claims.
        """
        # Keycloak nests realm roles under realm_access.roles
        realm_access = payload.get("realm_access", {})
        realm_roles = tuple(realm_access.get("roles", []))

        # Client roles under resource_access.{client_id}.roles
        resource_access = payload.get("resource_access", {})
        client_roles: list[str] = []
        for client_data in resource_access.values():
            client_roles.extend(client_data.get("roles", []))

        # Simple JWT fallback: "role" field
        if not realm_roles and "role" in payload:
            realm_roles = (payload["role"],)

        return KeycloakUser(
            sub=payload.get("sub", ""),
            username=payload.get("preferred_username", payload.get("sub", "")),
            email=payload.get("email", ""),
            realm_roles=realm_roles,
            client_roles=tuple(client_roles),
            groups=tuple(payload.get("groups", [])),
            name=payload.get("name", ""),
            given_name=payload.get("given_name", ""),
            family_name=payload.get("family_name", ""),
        )

    @property
    def config(self) -> KeycloakConfig:
        """Return the current configuration."""
        return self._config
