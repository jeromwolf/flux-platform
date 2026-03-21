"""Unit tests for Keycloak OIDC authentication bridge.

Tests cover KeycloakConfig, KeycloakUser, JWKSKeyCache, and
KeycloakTokenValidator without making network calls.

TC-KC01: KeycloakConfig
TC-KC02: KeycloakUser
TC-KC03: JWKSKeyCache
TC-KC04: KeycloakTokenValidator
"""

from __future__ import annotations

import time
from typing import Any, Optional

import pytest

from core.kg.api.middleware.keycloak import (
    JWKSKeyCache,
    KeycloakConfig,
    KeycloakTokenValidator,
    KeycloakUser,
)


# ---------------------------------------------------------------------------
# TC-KC01: KeycloakConfig
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestKeycloakConfig:
    """TC-KC01: KeycloakConfig construction and derived properties."""

    # TC-KC01a: Default config values
    def test_default_config_values(self):
        config = KeycloakConfig()
        assert config.server_url == ""
        assert config.realm == "imsp"
        assert config.client_id == "imsp-api"
        assert config.jwks_cache_ttl == 3600
        assert config.hs256_secret == ""
        assert config.algorithm == "RS256"

    # TC-KC01b: from_env() with KEYCLOAK_URL → RS256, without → HS256
    def test_from_env_with_keycloak_url_uses_rs256(self, monkeypatch):
        monkeypatch.setenv("KEYCLOAK_URL", "http://keycloak:8080")
        monkeypatch.delenv("KEYCLOAK_REALM", raising=False)
        monkeypatch.delenv("KEYCLOAK_CLIENT_ID", raising=False)
        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

        config = KeycloakConfig.from_env()
        assert config.server_url == "http://keycloak:8080"
        assert config.algorithm == "RS256"

    def test_from_env_without_keycloak_url_uses_hs256(self, monkeypatch):
        monkeypatch.delenv("KEYCLOAK_URL", raising=False)
        monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")

        config = KeycloakConfig.from_env()
        assert config.server_url == ""
        assert config.algorithm == "HS256"
        assert config.hs256_secret == "test-secret"

    def test_from_env_reads_realm_and_client_id(self, monkeypatch):
        monkeypatch.setenv("KEYCLOAK_URL", "http://keycloak:8080")
        monkeypatch.setenv("KEYCLOAK_REALM", "my-realm")
        monkeypatch.setenv("KEYCLOAK_CLIENT_ID", "my-client")
        monkeypatch.setenv("KEYCLOAK_JWKS_CACHE_TTL", "600")

        config = KeycloakConfig.from_env()
        assert config.realm == "my-realm"
        assert config.client_id == "my-client"
        assert config.jwks_cache_ttl == 600

    # TC-KC01c: is_keycloak_enabled property
    def test_is_keycloak_enabled_when_server_url_set(self):
        config = KeycloakConfig(server_url="http://keycloak:8080")
        assert config.is_keycloak_enabled is True

    def test_is_keycloak_enabled_false_when_server_url_empty(self):
        config = KeycloakConfig(server_url="")
        assert config.is_keycloak_enabled is False

    # TC-KC01d: Derived URLs
    def test_issuer_url(self):
        config = KeycloakConfig(server_url="http://keycloak:8080", realm="imsp")
        assert config.issuer_url == "http://keycloak:8080/realms/imsp"

    def test_issuer_url_strips_trailing_slash(self):
        config = KeycloakConfig(server_url="http://keycloak:8080/", realm="imsp")
        assert config.issuer_url == "http://keycloak:8080/realms/imsp"

    def test_issuer_url_empty_when_no_server_url(self):
        config = KeycloakConfig(server_url="")
        assert config.issuer_url == ""

    def test_jwks_url(self):
        config = KeycloakConfig(server_url="http://keycloak:8080", realm="imsp")
        assert config.jwks_url == (
            "http://keycloak:8080/realms/imsp/protocol/openid-connect/certs"
        )

    def test_token_url(self):
        config = KeycloakConfig(server_url="http://keycloak:8080", realm="imsp")
        assert config.token_url == (
            "http://keycloak:8080/realms/imsp/protocol/openid-connect/token"
        )

    def test_userinfo_url(self):
        config = KeycloakConfig(server_url="http://keycloak:8080", realm="imsp")
        assert config.userinfo_url == (
            "http://keycloak:8080/realms/imsp/protocol/openid-connect/userinfo"
        )

    def test_all_urls_empty_when_no_server_url(self):
        config = KeycloakConfig(server_url="")
        assert config.jwks_url == "/protocol/openid-connect/certs"
        # issuer_url is "" so derived URLs are just relative paths;
        # the important check is that issuer_url is empty
        assert config.issuer_url == ""

    # TC-KC01e: validate() errors when Keycloak enabled but missing realm/client_id
    def test_validate_no_errors_when_keycloak_enabled_and_config_complete(self):
        config = KeycloakConfig(
            server_url="http://keycloak:8080",
            realm="imsp",
            client_id="imsp-api",
        )
        assert config.validate() == []

    def test_validate_error_when_keycloak_enabled_and_realm_empty(self):
        config = KeycloakConfig(
            server_url="http://keycloak:8080",
            realm="",
            client_id="imsp-api",
        )
        errors = config.validate()
        assert any("KEYCLOAK_REALM" in e for e in errors)

    def test_validate_error_when_keycloak_enabled_and_client_id_empty(self):
        config = KeycloakConfig(
            server_url="http://keycloak:8080",
            realm="imsp",
            client_id="",
        )
        errors = config.validate()
        assert any("KEYCLOAK_CLIENT_ID" in e for e in errors)

    def test_validate_both_errors_when_realm_and_client_id_missing(self):
        config = KeycloakConfig(
            server_url="http://keycloak:8080",
            realm="",
            client_id="",
        )
        errors = config.validate()
        assert len(errors) == 2

    # TC-KC01f: validate() errors in HS256 mode with no secret
    def test_validate_error_in_hs256_mode_with_no_secret(self):
        config = KeycloakConfig(server_url="", hs256_secret="", algorithm="HS256")
        errors = config.validate()
        assert any("JWT_SECRET_KEY" in e for e in errors)

    def test_validate_no_errors_in_hs256_mode_with_secret(self):
        config = KeycloakConfig(
            server_url="", hs256_secret="my-secret", algorithm="HS256"
        )
        errors = config.validate()
        assert errors == []

    def test_validate_returns_list_type(self):
        config = KeycloakConfig()
        result = config.validate()
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# TC-KC02: KeycloakUser
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestKeycloakUser:
    """TC-KC02: KeycloakUser dataclass and primary_role logic."""

    # TC-KC02a: primary_role priority
    def test_primary_role_admin_beats_all(self):
        user = KeycloakUser(
            sub="u1",
            realm_roles=("viewer", "researcher", "admin"),
        )
        assert user.primary_role == "admin"

    def test_primary_role_researcher_beats_viewer(self):
        user = KeycloakUser(
            sub="u1",
            realm_roles=("viewer", "researcher"),
        )
        assert user.primary_role == "researcher"

    def test_primary_role_viewer_when_no_higher_role(self):
        user = KeycloakUser(sub="u1", realm_roles=("viewer",))
        assert user.primary_role == "viewer"

    def test_primary_role_first_realm_role_as_fallback(self):
        user = KeycloakUser(sub="u1", realm_roles=("operator", "monitor"))
        assert user.primary_role == "operator"

    def test_primary_role_admin_from_client_roles(self):
        user = KeycloakUser(
            sub="u1",
            realm_roles=("viewer",),
            client_roles=("admin",),
        )
        assert user.primary_role == "admin"

    def test_primary_role_combines_realm_and_client_roles(self):
        user = KeycloakUser(
            sub="u1",
            realm_roles=("viewer",),
            client_roles=("researcher",),
        )
        assert user.primary_role == "researcher"

    # TC-KC02b: primary_role returns "user" when no roles
    def test_primary_role_defaults_to_user_when_no_roles(self):
        user = KeycloakUser(sub="u1")
        assert user.primary_role == "user"

    def test_primary_role_user_when_both_role_tuples_empty(self):
        user = KeycloakUser(sub="u1", realm_roles=(), client_roles=())
        assert user.primary_role == "user"

    # TC-KC02c: frozen dataclass (immutable)
    def test_keycloak_user_is_frozen(self):
        user = KeycloakUser(sub="u1")
        with pytest.raises((AttributeError, TypeError)):
            user.sub = "u2"  # type: ignore[misc]

    def test_keycloak_user_realm_roles_is_tuple(self):
        user = KeycloakUser(sub="u1", realm_roles=("admin",))
        assert isinstance(user.realm_roles, tuple)

    def test_keycloak_user_client_roles_is_tuple(self):
        user = KeycloakUser(sub="u1", client_roles=("viewer",))
        assert isinstance(user.client_roles, tuple)

    def test_keycloak_user_groups_is_tuple(self):
        user = KeycloakUser(sub="u1", groups=("/maritime/analysts",))
        assert isinstance(user.groups, tuple)

    def test_keycloak_user_default_fields(self):
        user = KeycloakUser(sub="u1")
        assert user.username == ""
        assert user.email == ""
        assert user.name == ""
        assert user.given_name == ""
        assert user.family_name == ""
        assert user.realm_roles == ()
        assert user.client_roles == ()
        assert user.groups == ()


# ---------------------------------------------------------------------------
# TC-KC03: JWKSKeyCache
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestJWKSKeyCache:
    """TC-KC03: JWKSKeyCache TTL and state management."""

    # TC-KC03a: Cache is expired when empty
    def test_cache_expired_when_empty(self):
        cache = JWKSKeyCache(jwks_url="http://keycloak/certs", ttl=3600)
        assert cache._is_expired() is True

    def test_cache_not_expired_when_keys_present_within_ttl(self):
        cache = JWKSKeyCache(jwks_url="http://keycloak/certs", ttl=3600)
        # Inject fake keys and a recent fetch time
        cache._keys["kid-1"] = {"kid": "kid-1", "kty": "RSA"}
        cache._last_fetch = time.monotonic()
        assert cache._is_expired() is False

    def test_cache_expired_after_ttl(self):
        cache = JWKSKeyCache(jwks_url="http://keycloak/certs", ttl=3600)
        cache._keys["kid-1"] = {"kid": "kid-1", "kty": "RSA"}
        # Simulate a fetch that happened well in the past
        cache._last_fetch = time.monotonic() - 7200  # 2 hours ago
        assert cache._is_expired() is True

    # TC-KC03b: clear() resets cache
    def test_clear_removes_keys(self):
        cache = JWKSKeyCache(jwks_url="http://keycloak/certs", ttl=3600)
        cache._keys["kid-1"] = {"kid": "kid-1", "kty": "RSA"}
        cache._last_fetch = time.monotonic()
        cache.clear()
        assert cache._keys == {}
        assert cache._last_fetch == 0

    def test_cache_expired_after_clear(self):
        cache = JWKSKeyCache(jwks_url="http://keycloak/certs", ttl=3600)
        cache._keys["kid-1"] = {"kid": "kid-1"}
        cache._last_fetch = time.monotonic()
        cache.clear()
        assert cache._is_expired() is True

    # TC-KC03c: _is_expired after TTL (small TTL)
    def test_is_expired_after_small_ttl(self):
        cache = JWKSKeyCache(jwks_url="http://keycloak/certs", ttl=0)
        # Populate cache with a tiny TTL
        cache._keys["kid-1"] = {"kid": "kid-1"}
        cache._last_fetch = time.monotonic() - 1  # 1 second ago, TTL is 0
        assert cache._is_expired() is True

    def test_is_not_expired_immediately_after_fetch_with_large_ttl(self):
        cache = JWKSKeyCache(jwks_url="http://keycloak/certs", ttl=3600)
        cache._keys["kid-1"] = {"kid": "kid-1"}
        cache._last_fetch = time.monotonic()
        assert cache._is_expired() is False

    def test_get_key_returns_none_for_unknown_kid_after_failed_refresh(self):
        """When JWKS endpoint is unavailable and cache is empty, get_key raises."""
        cache = JWKSKeyCache(jwks_url="http://127.0.0.1:0/certs", ttl=3600)
        # _refresh will fail (no server), and since cache is empty it re-raises
        with pytest.raises(Exception):
            cache.get_key("unknown-kid")


# ---------------------------------------------------------------------------
# TC-KC04: KeycloakTokenValidator
# ---------------------------------------------------------------------------


def _make_hs256_token(
    payload: dict[str, Any],
    secret: str,
    algorithm: str = "HS256",
) -> str:
    """Helper: create a signed HS256 JWT using PyJWT."""
    import jwt as pyjwt

    return pyjwt.encode(payload, secret, algorithm=algorithm)


@pytest.mark.unit
class TestKeycloakTokenValidator:
    """TC-KC04: KeycloakTokenValidator validation logic."""

    # TC-KC04a: HS256 validation with valid token
    def test_hs256_validate_token_success(self):
        secret = "test-hs256-secret"
        payload = {
            "sub": "user-1",
            "preferred_username": "alice",
            "email": "alice@example.com",
        }
        token = _make_hs256_token(payload, secret)

        config = KeycloakConfig(server_url="", hs256_secret=secret, algorithm="HS256")
        validator = KeycloakTokenValidator(config)
        user = validator.validate_token(token)

        assert user.sub == "user-1"
        assert user.username == "alice"
        assert user.email == "alice@example.com"

    def test_hs256_validate_token_returns_keycloak_user(self):
        secret = "another-secret"
        payload = {"sub": "user-42"}
        token = _make_hs256_token(payload, secret)

        config = KeycloakConfig(server_url="", hs256_secret=secret, algorithm="HS256")
        validator = KeycloakTokenValidator(config)
        user = validator.validate_token(token)

        assert isinstance(user, KeycloakUser)

    # TC-KC04b: HS256 validation fails with wrong secret
    def test_hs256_validate_fails_with_wrong_secret(self):
        token = _make_hs256_token({"sub": "user-1"}, "correct-secret")

        config = KeycloakConfig(
            server_url="", hs256_secret="wrong-secret", algorithm="HS256"
        )
        validator = KeycloakTokenValidator(config)

        with pytest.raises(ValueError, match="[Ii]nvalid"):
            validator.validate_token(token)

    # TC-KC04c: HS256 raises ValueError when no secret configured
    def test_hs256_raises_when_no_secret_configured(self):
        config = KeycloakConfig(server_url="", hs256_secret="", algorithm="HS256")
        validator = KeycloakTokenValidator(config)

        with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
            validator.validate_token("any.token.here")

    # TC-KC04d: _extract_user handles Keycloak realm_access.roles
    def test_extract_user_handles_realm_access_roles(self):
        payload: dict[str, Any] = {
            "sub": "user-1",
            "preferred_username": "bob",
            "realm_access": {"roles": ["admin", "researcher"]},
        }
        user = KeycloakTokenValidator._extract_user(payload)
        assert "admin" in user.realm_roles
        assert "researcher" in user.realm_roles

    def test_extract_user_empty_realm_access(self):
        payload: dict[str, Any] = {
            "sub": "user-1",
            "realm_access": {},
        }
        user = KeycloakTokenValidator._extract_user(payload)
        assert user.realm_roles == ()

    # TC-KC04e: _extract_user handles simple "role" field fallback
    def test_extract_user_simple_role_field_fallback(self):
        payload: dict[str, Any] = {
            "sub": "user-1",
            "role": "viewer",
        }
        user = KeycloakTokenValidator._extract_user(payload)
        assert "viewer" in user.realm_roles

    def test_extract_user_role_fallback_not_used_when_realm_access_present(self):
        payload: dict[str, Any] = {
            "sub": "user-1",
            "role": "viewer",
            "realm_access": {"roles": ["admin"]},
        }
        user = KeycloakTokenValidator._extract_user(payload)
        # realm_access.roles should take precedence; "viewer" from role field
        # should NOT be added since realm_roles is non-empty
        assert "admin" in user.realm_roles
        assert "viewer" not in user.realm_roles

    # TC-KC04f: _extract_user handles resource_access for client_roles
    def test_extract_user_resource_access_client_roles(self):
        payload: dict[str, Any] = {
            "sub": "user-1",
            "resource_access": {
                "imsp-api": {"roles": ["read", "write"]},
                "other-client": {"roles": ["manage"]},
            },
        }
        user = KeycloakTokenValidator._extract_user(payload)
        assert "read" in user.client_roles
        assert "write" in user.client_roles
        assert "manage" in user.client_roles

    def test_extract_user_empty_resource_access(self):
        payload: dict[str, Any] = {"sub": "user-1", "resource_access": {}}
        user = KeycloakTokenValidator._extract_user(payload)
        assert user.client_roles == ()

    def test_extract_user_maps_name_fields(self):
        payload: dict[str, Any] = {
            "sub": "user-1",
            "name": "Alice Smith",
            "given_name": "Alice",
            "family_name": "Smith",
            "email": "alice@example.com",
            "preferred_username": "alice.smith",
        }
        user = KeycloakTokenValidator._extract_user(payload)
        assert user.name == "Alice Smith"
        assert user.given_name == "Alice"
        assert user.family_name == "Smith"
        assert user.email == "alice@example.com"
        assert user.username == "alice.smith"

    def test_extract_user_username_falls_back_to_sub(self):
        payload: dict[str, Any] = {"sub": "user-99"}
        user = KeycloakTokenValidator._extract_user(payload)
        assert user.username == "user-99"

    def test_extract_user_groups(self):
        payload: dict[str, Any] = {
            "sub": "user-1",
            "groups": ["/maritime/analysts", "/admin"],
        }
        user = KeycloakTokenValidator._extract_user(payload)
        assert "/maritime/analysts" in user.groups
        assert "/admin" in user.groups

    # TC-KC04g: Keycloak mode sets up JWKS cache
    def test_keycloak_mode_initialises_jwks_cache(self):
        config = KeycloakConfig(
            server_url="http://keycloak:8080",
            realm="imsp",
            client_id="imsp-api",
        )
        validator = KeycloakTokenValidator(config)
        assert validator._jwks_cache is not None
        assert isinstance(validator._jwks_cache, JWKSKeyCache)

    def test_hs256_mode_does_not_create_jwks_cache(self):
        config = KeycloakConfig(
            server_url="",
            hs256_secret="secret",
            algorithm="HS256",
        )
        validator = KeycloakTokenValidator(config)
        assert validator._jwks_cache is None

    def test_config_property_returns_config(self):
        config = KeycloakConfig(server_url="", hs256_secret="sec", algorithm="HS256")
        validator = KeycloakTokenValidator(config)
        assert validator.config is config
