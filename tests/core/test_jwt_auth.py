"""Unit tests for JWT authentication middleware.

Tests cover token creation, decoding, validation, the FastAPI dependency
function, and the unified ``get_current_user`` auth dependency.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from kg.api.middleware.jwt_auth import (
    JWTPayload,
    _decode_jwt,
    create_token,
    get_jwt_payload,
)
from kg.config import AppConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decode_jwt_with_secret(token: str, secret: str) -> dict:
    """Helper to decode JWT with a specific secret."""
    import jwt as pyjwt

    return pyjwt.decode(token, secret, algorithms=["HS256"], options={"verify_iss": False})


# ---------------------------------------------------------------------------
# Token creation tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateToken:
    """Tests for JWT token creation."""

    def test_create_token_returns_string(self):
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret"}):
            token = create_token(sub="user-1", role="admin")
        assert isinstance(token, str)
        assert len(token.split(".")) == 3  # JWT has 3 parts

    def test_create_token_with_custom_expiry(self):
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret"}):
            token = create_token(sub="user-1", expires_in=7200)
        payload = _decode_jwt_with_secret(token, "test-secret")
        assert payload["exp"] - payload["iat"] == 7200

    def test_create_token_includes_role(self):
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret"}):
            token = create_token(sub="user-1", role="researcher")
        payload = _decode_jwt_with_secret(token, "test-secret")
        assert payload["role"] == "researcher"

    def test_create_token_includes_extra_claims(self):
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret"}):
            token = create_token(sub="user-1", extra={"department": "maritime"})
        payload = _decode_jwt_with_secret(token, "test-secret")
        assert payload["department"] == "maritime"

    def test_create_token_default_role_is_user(self):
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret"}):
            token = create_token(sub="user-1")
        payload = _decode_jwt_with_secret(token, "test-secret")
        assert payload["role"] == "user"

    def test_create_token_with_issuer(self):
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret", "JWT_ISSUER": "my-app"}):
            token = create_token(sub="user-1")
        payload = _decode_jwt_with_secret(token, "test-secret")
        assert payload["iss"] == "my-app"

    def test_create_token_without_issuer_has_no_iss(self):
        env = {"JWT_SECRET_KEY": "test-secret"}
        with patch.dict(os.environ, env, clear=False):
            # Ensure JWT_ISSUER is not set
            os.environ.pop("JWT_ISSUER", None)
            token = create_token(sub="user-1")
        payload = _decode_jwt_with_secret(token, "test-secret")
        assert "iss" not in payload


# ---------------------------------------------------------------------------
# Token decoding tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDecodeJWT:
    """Tests for JWT token decoding."""

    def test_decode_valid_token(self):
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret"}):
            token = create_token(sub="user-1", role="admin")
            payload = _decode_jwt(token)
        assert payload["sub"] == "user-1"
        assert payload["role"] == "admin"

    def test_decode_expired_token_raises(self):
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret"}):
            token = create_token(sub="user-1", expires_in=-10)
            with pytest.raises(ValueError, match="expired"):
                _decode_jwt(token)

    def test_decode_invalid_format_raises(self):
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret"}):
            with pytest.raises((ValueError, Exception)):
                _decode_jwt("not-a-jwt-token")

    def test_decode_wrong_secret_raises(self):
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "correct-secret"}):
            token = create_token(sub="user-1")
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "wrong-secret"}):
            with pytest.raises((ValueError, Exception)):
                _decode_jwt(token)

    def test_decode_preserves_all_claims(self):
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret"}):
            token = create_token(sub="u1", role="admin", extra={"org": "kriso"})
            payload = _decode_jwt(token)
        assert payload["sub"] == "u1"
        assert payload["role"] == "admin"
        assert payload["org"] == "kriso"
        assert "iat" in payload
        assert "exp" in payload


# ---------------------------------------------------------------------------
# JWTPayload dataclass tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestJWTPayload:
    """Tests for JWTPayload dataclass."""

    def test_jwt_payload_creation(self):
        payload = JWTPayload(sub="user-1", role="admin", exp=9999999999)
        assert payload.sub == "user-1"
        assert payload.role == "admin"
        assert payload.exp == 9999999999

    def test_jwt_payload_frozen(self):
        payload = JWTPayload(sub="user-1", role="admin", exp=0)
        with pytest.raises(AttributeError):
            payload.sub = "other"  # type: ignore[misc]

    def test_jwt_payload_defaults(self):
        payload = JWTPayload(sub="user-1", role="user", exp=0)
        assert payload.iss == ""
        assert payload.iat == 0
        assert payload.extra == {}

    def test_jwt_payload_with_extra(self):
        payload = JWTPayload(
            sub="user-1", role="admin", exp=0, extra={"department": "maritime"}
        )
        assert payload.extra["department"] == "maritime"


# ---------------------------------------------------------------------------
# FastAPI dependency tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetJWTPayload:
    """Tests for the FastAPI dependency function."""

    def test_dev_mode_returns_none(self):
        dev_config = AppConfig(env="development")
        result = get_jwt_payload(credentials=None, config=dev_config)
        assert result is None

    def test_no_credentials_returns_none(self):
        prod_config = AppConfig(env="production")
        result = get_jwt_payload(credentials=None, config=prod_config)
        assert result is None

    def test_valid_token_returns_payload(self):
        from fastapi.security import HTTPAuthorizationCredentials

        prod_config = AppConfig(env="production")
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret"}):
            token = create_token(sub="user-1", role="researcher")
            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            result = get_jwt_payload(credentials=creds, config=prod_config)

        assert result is not None
        assert result.sub == "user-1"
        assert result.role == "researcher"

    def test_expired_token_raises_401(self):
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        prod_config = AppConfig(env="production")
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret"}):
            token = create_token(sub="user-1", expires_in=-10)
            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            with pytest.raises(HTTPException) as exc_info:
                get_jwt_payload(credentials=creds, config=prod_config)
            assert exc_info.value.status_code == 401

    def test_invalid_token_raises_401(self):
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        prod_config = AppConfig(env="production")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid.token.here")
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret"}):
            with pytest.raises(HTTPException) as exc_info:
                get_jwt_payload(credentials=creds, config=prod_config)
            assert exc_info.value.status_code == 401

    def test_dev_mode_ignores_valid_token(self):
        from fastapi.security import HTTPAuthorizationCredentials

        dev_config = AppConfig(env="development")
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret"}):
            token = create_token(sub="user-1", role="admin")
            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            result = get_jwt_payload(credentials=creds, config=dev_config)
        assert result is None

    def test_valid_token_extracts_iss(self):
        from fastapi.security import HTTPAuthorizationCredentials

        prod_config = AppConfig(env="production")
        with patch.dict(
            os.environ, {"JWT_SECRET_KEY": "test-secret", "JWT_ISSUER": "maritime-platform"}
        ):
            token = create_token(sub="user-1", role="admin")
            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            result = get_jwt_payload(credentials=creds, config=prod_config)

        assert result is not None
        assert result.iss == "maritime-platform"


# ---------------------------------------------------------------------------
# Unified auth dependency tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestUnifiedAuth:
    """Tests for the unified get_current_user dependency."""

    def test_dev_mode_returns_dev_user(self):
        from kg.api.middleware.auth import get_current_user

        dev_config = AppConfig(env="development")
        result = get_current_user(jwt_payload=None, api_key=None, config=dev_config)
        assert result["sub"] == "dev-user"
        assert result["role"] == "admin"
        assert result["auth_method"] == "dev-bypass"

    def test_jwt_takes_priority(self):
        from kg.api.middleware.auth import get_current_user

        prod_config = AppConfig(env="production")
        jwt = JWTPayload(sub="jwt-user", role="researcher", exp=9999999999)
        result = get_current_user(jwt_payload=jwt, api_key="some-key", config=prod_config)
        assert result["sub"] == "jwt-user"
        assert result["role"] == "researcher"
        assert result["auth_method"] == "jwt"

    def test_api_key_fallback(self):
        from kg.api.middleware.auth import get_current_user

        prod_config = AppConfig(env="production")
        result = get_current_user(jwt_payload=None, api_key="valid-key", config=prod_config)
        assert result["sub"] == "api-key-user"
        assert result["role"] == "viewer"  # unregistered keys default to viewer
        assert result["auth_method"] == "api-key"

    def test_no_auth_raises_401(self):
        from fastapi import HTTPException

        from kg.api.middleware.auth import get_current_user

        prod_config = AppConfig(env="production")
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(jwt_payload=None, api_key=None, config=prod_config)
        assert exc_info.value.status_code == 401
        assert "Authentication required" in exc_info.value.detail

    def test_jwt_only_no_api_key(self):
        from kg.api.middleware.auth import get_current_user

        prod_config = AppConfig(env="production")
        jwt = JWTPayload(sub="jwt-only-user", role="admin", exp=9999999999)
        result = get_current_user(jwt_payload=jwt, api_key=None, config=prod_config)
        assert result["auth_method"] == "jwt"
        assert result["sub"] == "jwt-only-user"
