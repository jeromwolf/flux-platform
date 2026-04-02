"""Tests for JWT dual-mode authentication (HS256 + RS256/JWKS).

Covers:
- HS256 mode (no KEYCLOAK_URL) — existing behavior
- RS256 mode (with KEYCLOAK_URL) — mock JWKS
- JWKS fetch failure → HS256 fallback
- JWTPayload.roles extraction from realm_access
- JWKS cache TTL behavior
- create_token still works in HS256 mode
"""

from __future__ import annotations

import json
import time
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_hs256_token(sub: str = "user1", role: str = "admin", extra: dict | None = None) -> str:
    """Create a real HS256 token for testing."""
    import os

    os.environ["JWT_SECRET_KEY"] = "test-secret-key"
    os.environ.pop("JWT_ALGORITHM", None)

    from kg.api.middleware.jwt_auth import create_token

    return create_token(sub=sub, role=role, extra=extra or {})


def _make_rs256_token_and_key() -> tuple[str, Any, dict[str, Any]]:
    """Create a real RS256 key pair + JWT + JWKS for testing.

    Returns:
        (token_str, private_key, jwks_dict)
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    import jwt as pyjwt

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    # Build minimal JWKS
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from jwt.algorithms import RSAAlgorithm
    import base64

    pub_numbers = public_key.public_key().public_numbers() if hasattr(public_key, 'public_key') else public_key.public_numbers()

    def _int_to_base64url(n: int) -> str:
        length = (n.bit_length() + 7) // 8
        return base64.urlsafe_b64encode(n.to_bytes(length, "big")).rstrip(b"=").decode()

    jwks: dict[str, Any] = {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": "test-kid-1",
                "n": _int_to_base64url(pub_numbers.n),
                "e": _int_to_base64url(pub_numbers.e),
            }
        ]
    }

    # Create token
    now = int(time.time())
    payload = {
        "sub": "keycloak-user",
        "role": "user",
        "iat": now,
        "exp": now + 3600,
        "iss": "http://keycloak:8080/realms/imsp",
        "realm_access": {"roles": ["offline_access", "kg-reader"]},
    }

    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    token = pyjwt.encode(payload, pem, algorithm="RS256", headers={"kid": "test-kid-1"})
    return token, private_key, jwks


# ---------------------------------------------------------------------------
# Module-level cache reset fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_jwks_cache():
    """Reset module-level JWKS cache between tests."""
    import kg.api.middleware.jwt_auth as mod

    mod._jwks_cache = None
    mod._jwks_cached_at = 0.0
    yield
    mod._jwks_cache = None
    mod._jwks_cached_at = 0.0


# ---------------------------------------------------------------------------
# JWTPayload dataclass
# ---------------------------------------------------------------------------


class TestJWTPayload:
    def test_default_roles_empty(self):
        from kg.api.middleware.jwt_auth import JWTPayload

        p = JWTPayload(sub="u1", role="user", exp=9999)
        assert p.roles == []

    def test_roles_set_correctly(self):
        from kg.api.middleware.jwt_auth import JWTPayload

        p = JWTPayload(sub="u1", role="user", exp=9999, roles=["kg-reader", "kg-writer"])
        assert "kg-reader" in p.roles
        assert "kg-writer" in p.roles

    def test_frozen_raises_on_mutation(self):
        from kg.api.middleware.jwt_auth import JWTPayload

        p = JWTPayload(sub="u1", role="user", exp=9999)
        with pytest.raises((AttributeError, TypeError)):
            p.roles = ["new-role"]  # type: ignore[misc]

    def test_extra_field_preserved(self):
        from kg.api.middleware.jwt_auth import JWTPayload

        p = JWTPayload(sub="u1", role="user", exp=9999, extra={"tenant": "acme"})
        assert p.extra["tenant"] == "acme"


# ---------------------------------------------------------------------------
# create_token (HS256 only)
# ---------------------------------------------------------------------------


class TestCreateToken:
    def test_creates_valid_hs256_token(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "supersecret")
        monkeypatch.delenv("KEYCLOAK_URL", raising=False)

        from kg.api.middleware.jwt_auth import create_token

        token = create_token(sub="alice", role="admin")
        assert isinstance(token, str)
        assert len(token.split(".")) == 3

    def test_token_is_decodable_with_same_secret(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "supersecret")
        monkeypatch.delenv("KEYCLOAK_URL", raising=False)

        import jwt as pyjwt

        from kg.api.middleware.jwt_auth import create_token

        token = create_token(sub="bob", role="viewer", expires_in=600)
        payload = pyjwt.decode(token, "supersecret", algorithms=["HS256"])
        assert payload["sub"] == "bob"
        assert payload["role"] == "viewer"
        assert payload["exp"] - payload["iat"] == 600

    def test_create_token_requires_secret(self, monkeypatch):
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

        from kg.api.middleware.jwt_auth import create_token

        with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
            create_token(sub="x")

    def test_create_token_includes_extra(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "key")
        import jwt as pyjwt

        from kg.api.middleware.jwt_auth import create_token

        token = create_token(sub="u", extra={"tenant": "acme"})
        payload = pyjwt.decode(token, "key", algorithms=["HS256"])
        assert payload["tenant"] == "acme"

    def test_create_token_works_even_when_keycloak_url_set(self, monkeypatch):
        """create_token must use HS256 regardless of KEYCLOAK_URL."""
        monkeypatch.setenv("JWT_SECRET_KEY", "key")
        monkeypatch.setenv("KEYCLOAK_URL", "http://keycloak:8080")

        import jwt as pyjwt

        from kg.api.middleware.jwt_auth import create_token

        token = create_token(sub="u2", role="admin")
        # Should still be verifiable with HS256
        payload = pyjwt.decode(token, "key", algorithms=["HS256"])
        assert payload["sub"] == "u2"


# ---------------------------------------------------------------------------
# HS256 mode (_decode_jwt with no KEYCLOAK_URL)
# ---------------------------------------------------------------------------


class TestHS256Mode:
    def test_valid_token_decoded(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "mysecret")
        monkeypatch.delenv("KEYCLOAK_URL", raising=False)

        from kg.api.middleware.jwt_auth import _decode_jwt, create_token

        token = create_token(sub="charlie", role="analyst")
        payload = _decode_jwt(token)
        assert payload["sub"] == "charlie"
        assert payload["role"] == "analyst"

    def test_expired_token_raises(self, monkeypatch):
        import jwt as pyjwt

        monkeypatch.setenv("JWT_SECRET_KEY", "mysecret")
        monkeypatch.delenv("KEYCLOAK_URL", raising=False)

        from kg.api.middleware.jwt_auth import _decode_jwt

        now = int(time.time())
        expired_token = pyjwt.encode(
            {"sub": "x", "exp": now - 10, "iat": now - 70},
            "mysecret",
            algorithm="HS256",
        )
        with pytest.raises(ValueError, match="Token expired"):
            _decode_jwt(expired_token)

    def test_invalid_signature_raises(self, monkeypatch):
        import jwt as pyjwt

        monkeypatch.setenv("JWT_SECRET_KEY", "correct-secret")
        monkeypatch.delenv("KEYCLOAK_URL", raising=False)

        from kg.api.middleware.jwt_auth import _decode_jwt

        bad_token = pyjwt.encode({"sub": "x", "exp": int(time.time()) + 3600}, "wrong-secret")
        with pytest.raises(ValueError, match="Invalid token"):
            _decode_jwt(bad_token)

    def test_no_secret_raises(self, monkeypatch):
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        monkeypatch.delenv("KEYCLOAK_URL", raising=False)

        from kg.api.middleware.jwt_auth import _decode_jwt

        with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
            _decode_jwt("any.token.here")

    def test_issuer_verified_when_set(self, monkeypatch):
        import jwt as pyjwt

        monkeypatch.setenv("JWT_SECRET_KEY", "s")
        monkeypatch.setenv("JWT_ISSUER", "https://expected-issuer")
        monkeypatch.delenv("KEYCLOAK_URL", raising=False)

        from kg.api.middleware.jwt_auth import _decode_jwt

        bad_issuer_token = pyjwt.encode(
            {"sub": "x", "exp": int(time.time()) + 3600, "iss": "https://wrong-issuer"},
            "s",
        )
        with pytest.raises(ValueError, match="Invalid token"):
            _decode_jwt(bad_issuer_token)


# ---------------------------------------------------------------------------
# RS256 / Keycloak OIDC mode
# ---------------------------------------------------------------------------


class TestRS256Mode:
    @pytest.fixture()
    def rs256_setup(self, monkeypatch):
        """Set env vars for RS256 mode and produce a real RS256 token + JWKS."""
        pytest.importorskip("cryptography")

        monkeypatch.setenv("KEYCLOAK_URL", "http://keycloak:8080")
        monkeypatch.setenv("KEYCLOAK_REALM", "imsp")
        monkeypatch.setenv("KEYCLOAK_CLIENT_ID", "imsp-api")
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

        token, _key, jwks = _make_rs256_token_and_key()
        return token, jwks

    def _mock_urlopen(self, jwks: dict[str, Any]):
        """Return a mock context-manager for urllib.request.urlopen."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(jwks).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_valid_rs256_token_decoded(self, rs256_setup):
        token, jwks = rs256_setup

        from kg.api.middleware.jwt_auth import _decode_jwt

        with patch("urllib.request.urlopen", return_value=self._mock_urlopen(jwks)):
            payload = _decode_jwt(token)

        assert payload["sub"] == "keycloak-user"
        assert payload["iss"] == "http://keycloak:8080/realms/imsp"

    def test_rs256_roles_extracted(self, rs256_setup):
        token, jwks = rs256_setup

        from kg.api.middleware.jwt_auth import _decode_jwt

        with patch("urllib.request.urlopen", return_value=self._mock_urlopen(jwks)):
            payload = _decode_jwt(token)

        roles = payload.get("realm_access", {}).get("roles", [])
        assert "kg-reader" in roles
        assert "offline_access" in roles

    def test_wrong_kid_falls_back_to_hs256(self, monkeypatch):
        """When kid doesn't match JWKS, falls back to HS256 (migration period)."""
        pytest.importorskip("cryptography")

        monkeypatch.setenv("KEYCLOAK_URL", "http://keycloak:8080")
        monkeypatch.setenv("JWT_SECRET_KEY", "hs256-secret")
        monkeypatch.delenv("JWT_ISSUER", raising=False)

        import jwt as pyjwt

        # Create an HS256 token (simulating migration: old token format)
        hs256_token = pyjwt.encode(
            {"sub": "migrating-user", "exp": int(time.time()) + 3600},
            "hs256-secret",
            algorithm="HS256",
        )

        token_rs256, _key, jwks = _make_rs256_token_and_key()
        # Replace kid in JWKS with a different one so RS256 fails
        jwks["keys"][0]["kid"] = "different-kid"

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(jwks).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        from kg.api.middleware.jwt_auth import _decode_jwt

        # HS256 token should succeed via fallback when kid doesn't match
        with patch("urllib.request.urlopen", return_value=mock_resp):
            payload = _decode_jwt(hs256_token)

        assert payload["sub"] == "migrating-user"


# ---------------------------------------------------------------------------
# JWKS fetch failure → HS256 fallback
# ---------------------------------------------------------------------------


class TestJWKSFallback:
    def test_falls_back_to_hs256_when_jwks_fetch_fails(self, monkeypatch):
        """When KEYCLOAK_URL is set but JWKS is unreachable → HS256 fallback."""
        monkeypatch.setenv("KEYCLOAK_URL", "http://unreachable-keycloak:8080")
        monkeypatch.setenv("JWT_SECRET_KEY", "fallback-secret")
        monkeypatch.delenv("JWT_ISSUER", raising=False)

        import jwt as pyjwt

        from kg.api.middleware.jwt_auth import _decode_jwt

        # Create a valid HS256 token
        token = pyjwt.encode(
            {"sub": "fallback-user", "role": "user", "exp": int(time.time()) + 3600},
            "fallback-secret",
            algorithm="HS256",
        )

        # JWKS fetch fails with network error
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            payload = _decode_jwt(token)

        assert payload["sub"] == "fallback-user"

    def test_falls_back_to_hs256_when_no_matching_kid(self, monkeypatch):
        """No matching kid in JWKS → falls back to HS256."""
        monkeypatch.setenv("KEYCLOAK_URL", "http://keycloak:8080")
        monkeypatch.setenv("JWT_SECRET_KEY", "hs256-key")
        monkeypatch.delenv("JWT_ISSUER", raising=False)

        import jwt as pyjwt

        from kg.api.middleware.jwt_auth import _decode_jwt

        # Valid HS256 token
        token = pyjwt.encode(
            {"sub": "hs256-fallback", "exp": int(time.time()) + 3600},
            "hs256-key",
            algorithm="HS256",
        )

        # JWKS returns keys, but none match the HS256 token's kid (which is None)
        empty_jwks = {"keys": [{"kid": "some-other-kid", "kty": "RSA"}]}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(empty_jwks).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            payload = _decode_jwt(token)

        assert payload["sub"] == "hs256-fallback"

    def test_expired_token_is_not_silently_accepted_after_fallback(self, monkeypatch):
        """Even in HS256 fallback mode, an expired token must be rejected."""
        monkeypatch.setenv("KEYCLOAK_URL", "http://unreachable:8080")
        monkeypatch.setenv("JWT_SECRET_KEY", "key")
        monkeypatch.delenv("JWT_ISSUER", raising=False)

        import jwt as pyjwt

        from kg.api.middleware.jwt_auth import _decode_jwt

        expired = pyjwt.encode(
            {"sub": "x", "exp": int(time.time()) - 100},
            "key",
            algorithm="HS256",
        )

        with patch("urllib.request.urlopen", side_effect=OSError("fail")):
            with pytest.raises(ValueError, match="Token expired"):
                _decode_jwt(expired)


# ---------------------------------------------------------------------------
# JWKS cache TTL
# ---------------------------------------------------------------------------


class TestJWKSCache:
    def _mock_urlopen_call(self, jwks: dict[str, Any]):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(jwks).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_jwks_cached_on_first_fetch(self, monkeypatch):
        monkeypatch.setenv("KEYCLOAK_URL", "http://keycloak:8080")
        monkeypatch.setenv("KEYCLOAK_REALM", "imsp")

        from kg.api.middleware.jwt_auth import _fetch_jwks

        jwks = {"keys": [{"kid": "k1"}]}

        with patch("urllib.request.urlopen", return_value=self._mock_urlopen_call(jwks)) as m:
            result1 = _fetch_jwks()
            result2 = _fetch_jwks()  # should use cache

        assert result1 == jwks
        assert result2 == jwks
        assert m.call_count == 1  # fetched only once

    def test_jwks_refetched_after_ttl_expires(self, monkeypatch):
        monkeypatch.setenv("KEYCLOAK_URL", "http://keycloak:8080")
        monkeypatch.setenv("KEYCLOAK_REALM", "imsp")

        import kg.api.middleware.jwt_auth as mod
        from kg.api.middleware.jwt_auth import _fetch_jwks

        jwks = {"keys": [{"kid": "k2"}]}

        with patch("urllib.request.urlopen", return_value=self._mock_urlopen_call(jwks)) as m:
            # Simulate first fetch
            result1 = _fetch_jwks()
            assert m.call_count == 1

            # Wind the clock forward past TTL
            mod._jwks_cached_at = time.time() - (mod._JWKS_CACHE_TTL + 1)

            result2 = _fetch_jwks()
            assert m.call_count == 2

        assert result1 == result2

    def test_jwks_cache_survives_within_ttl(self, monkeypatch):
        monkeypatch.setenv("KEYCLOAK_URL", "http://keycloak:8080")

        import kg.api.middleware.jwt_auth as mod
        from kg.api.middleware.jwt_auth import _fetch_jwks

        jwks = {"keys": [{"kid": "k3"}]}
        with patch("urllib.request.urlopen", return_value=self._mock_urlopen_call(jwks)) as m:
            _fetch_jwks()
            # Still within TTL window
            mod._jwks_cached_at = time.time() - (mod._JWKS_CACHE_TTL - 60)
            _fetch_jwks()

        assert m.call_count == 1

    def test_failed_fetch_does_not_populate_cache(self, monkeypatch):
        monkeypatch.setenv("KEYCLOAK_URL", "http://keycloak:8080")

        import kg.api.middleware.jwt_auth as mod
        from kg.api.middleware.jwt_auth import _fetch_jwks

        with patch("urllib.request.urlopen", side_effect=OSError("fail")):
            result = _fetch_jwks()

        assert result is None
        assert mod._jwks_cache is None  # cache NOT populated on failure

    def test_jwks_uri_uses_realm_env(self, monkeypatch):
        monkeypatch.setenv("KEYCLOAK_URL", "http://auth.example.com")
        monkeypatch.setenv("KEYCLOAK_REALM", "maritime")

        from kg.api.middleware.jwt_auth import _jwks_uri

        uri = _jwks_uri()
        assert uri == "http://auth.example.com/realms/maritime/protocol/openid-connect/certs"

    def test_jwks_uri_default_realm(self, monkeypatch):
        monkeypatch.setenv("KEYCLOAK_URL", "http://kc:8080")
        monkeypatch.delenv("KEYCLOAK_REALM", raising=False)

        from kg.api.middleware.jwt_auth import _jwks_uri

        assert "/realms/imsp/" in _jwks_uri()


# ---------------------------------------------------------------------------
# get_jwt_payload dependency — roles extraction
# ---------------------------------------------------------------------------


class TestGetJWTPayloadRoles:
    def _make_app_config(self, env: str = "production"):
        from unittest.mock import MagicMock

        cfg = MagicMock()
        cfg.env = env
        return cfg

    def test_roles_extracted_from_realm_access(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "secret")
        monkeypatch.delenv("KEYCLOAK_URL", raising=False)

        import jwt as pyjwt

        from kg.api.middleware.jwt_auth import get_jwt_payload

        token = pyjwt.encode(
            {
                "sub": "user42",
                "role": "admin",
                "exp": int(time.time()) + 3600,
                "realm_access": {"roles": ["kg-reader", "kg-writer"]},
            },
            "secret",
            algorithm="HS256",
        )

        creds = MagicMock()
        creds.credentials = token
        config = self._make_app_config("production")

        result = get_jwt_payload(credentials=creds, config=config)

        assert result is not None
        assert "kg-reader" in result.roles
        assert "kg-writer" in result.roles

    def test_roles_empty_when_no_realm_access(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "secret")
        monkeypatch.delenv("KEYCLOAK_URL", raising=False)

        import jwt as pyjwt

        from kg.api.middleware.jwt_auth import get_jwt_payload

        token = pyjwt.encode(
            {"sub": "u", "role": "user", "exp": int(time.time()) + 3600},
            "secret",
            algorithm="HS256",
        )

        creds = MagicMock()
        creds.credentials = token
        config = self._make_app_config("production")

        result = get_jwt_payload(credentials=creds, config=config)

        assert result is not None
        assert result.roles == []

    def test_dev_mode_returns_none(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "secret")

        from kg.api.middleware.jwt_auth import get_jwt_payload

        creds = MagicMock()
        config = self._make_app_config("development")

        result = get_jwt_payload(credentials=creds, config=config)
        assert result is None

    def test_no_credentials_returns_none(self, monkeypatch):
        from kg.api.middleware.jwt_auth import get_jwt_payload

        config = self._make_app_config("production")
        result = get_jwt_payload(credentials=None, config=config)
        assert result is None

    def test_invalid_token_raises_401(self, monkeypatch):
        from fastapi import HTTPException

        monkeypatch.setenv("JWT_SECRET_KEY", "secret")
        monkeypatch.delenv("KEYCLOAK_URL", raising=False)

        from kg.api.middleware.jwt_auth import get_jwt_payload

        creds = MagicMock()
        creds.credentials = "not.a.valid.jwt"
        config = self._make_app_config("production")

        with pytest.raises(HTTPException) as exc_info:
            get_jwt_payload(credentials=creds, config=config)

        assert exc_info.value.status_code == 401

    def test_sub_and_role_extracted(self, monkeypatch):
        monkeypatch.setenv("JWT_SECRET_KEY", "s")
        monkeypatch.delenv("KEYCLOAK_URL", raising=False)

        import jwt as pyjwt

        from kg.api.middleware.jwt_auth import get_jwt_payload

        token = pyjwt.encode(
            {"sub": "alice", "role": "superadmin", "exp": int(time.time()) + 3600},
            "s",
        )
        creds = MagicMock()
        creds.credentials = token
        config = self._make_app_config("production")

        result = get_jwt_payload(credentials=creds, config=config)
        assert result is not None
        assert result.sub == "alice"
        assert result.role == "superadmin"
