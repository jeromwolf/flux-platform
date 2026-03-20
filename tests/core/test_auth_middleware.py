"""Unit tests for API authentication middleware.

Tests cover development mode bypass, production mode enforcement,
environment variable configuration, and integration with FastAPI endpoints.
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from kg.api.app import create_app
from kg.api.deps import get_app_config, get_async_neo4j_session
from kg.api.middleware.auth import get_current_api_key
from kg.config import AppConfig, Neo4jConfig, reset

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_config():
    """Reset config singleton before/after each test."""
    reset()
    yield
    reset()


@pytest.fixture
def dev_config() -> AppConfig:
    """AppConfig for development mode."""
    return AppConfig(
        env="development",
        neo4j=Neo4jConfig(uri="bolt://mock:7687"),
    )


@pytest.fixture
def prod_config() -> AppConfig:
    """AppConfig for production mode."""
    return AppConfig(
        env="production",
        neo4j=Neo4jConfig(uri="bolt://mock:7687"),
    )


def _make_async_mock_result(records: list | None = None, single_value: Any = None) -> MagicMock:
    """Create a mock async result that supports ``async for`` and ``await .single()``."""
    mock_result = MagicMock()
    _records = records if records is not None else []

    async def _aiter_impl():
        for r in _records:
            yield r

    mock_result.__aiter__ = lambda self: _aiter_impl()
    mock_result.single = AsyncMock(return_value=single_value)
    return mock_result


def _make_mock_session() -> MagicMock:
    """Create a mock async Neo4j session."""
    mock_session = MagicMock()
    mock_session.run = AsyncMock()
    mock_session.close = AsyncMock()
    return mock_session


# ---------------------------------------------------------------------------
# Development mode tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAuthMiddlewareDevelopment:
    """Test authentication behavior in development mode."""

    def test_dev_mode_without_api_key_returns_none(self, dev_config: AppConfig):
        """In dev mode, get_current_api_key returns None when no key provided."""
        result = get_current_api_key(api_key=None, config=dev_config)
        assert result is None

    def test_dev_mode_with_invalid_key_returns_none(self, dev_config: AppConfig):
        """In dev mode, get_current_api_key returns None even with wrong key."""
        with patch.dict(os.environ, {"APP_API_KEY": "correct-key"}):
            result = get_current_api_key(api_key="wrong-key", config=dev_config)
        assert result is None

    def test_dev_mode_with_correct_key_returns_none(self, dev_config: AppConfig):
        """In dev mode, get_current_api_key returns None even with correct key."""
        with patch.dict(os.environ, {"APP_API_KEY": "correct-key"}):
            result = get_current_api_key(api_key="correct-key", config=dev_config)
        assert result is None

    def test_dev_mode_ignores_env_variable(self, dev_config: AppConfig):
        """In dev mode, APP_API_KEY environment variable is ignored."""
        with patch.dict(os.environ, {"APP_API_KEY": "should-be-ignored"}):
            result = get_current_api_key(api_key=None, config=dev_config)
        assert result is None

    def test_dev_mode_with_empty_string_key_returns_none(self, dev_config: AppConfig):
        """In dev mode, empty string API key returns None."""
        result = get_current_api_key(api_key="", config=dev_config)
        assert result is None


# ---------------------------------------------------------------------------
# Production mode tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAuthMiddlewareProduction:
    """Test authentication behavior in production mode."""

    def test_prod_mode_without_api_key_raises_401(self, prod_config: AppConfig):
        """In production mode, missing API key raises HTTPException(401)."""
        with patch.dict(os.environ, {"APP_API_KEY": "secret-key"}):
            with pytest.raises(HTTPException) as exc_info:
                get_current_api_key(api_key=None, config=prod_config)
            assert exc_info.value.status_code == 401
            assert "Invalid or missing API key" in exc_info.value.detail

    def test_prod_mode_with_wrong_key_raises_401(self, prod_config: AppConfig):
        """In production mode, incorrect API key raises HTTPException(401)."""
        with patch.dict(os.environ, {"APP_API_KEY": "correct-key"}):
            with pytest.raises(HTTPException) as exc_info:
                get_current_api_key(api_key="wrong-key", config=prod_config)
            assert exc_info.value.status_code == 401
            assert "Invalid or missing API key" in exc_info.value.detail

    def test_prod_mode_with_correct_key_returns_key(self, prod_config: AppConfig):
        """In production mode, correct API key is returned."""
        with patch.dict(os.environ, {"APP_API_KEY": "correct-key"}):
            result = get_current_api_key(api_key="correct-key", config=prod_config)
        assert result == "correct-key"

    def test_prod_mode_without_env_variable_raises_500(self, prod_config: AppConfig):
        """In production mode, if APP_API_KEY not set, raises HTTPException(500)."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(HTTPException) as exc_info:
                get_current_api_key(api_key=None, config=prod_config)
            assert exc_info.value.status_code == 500
            assert "API key not set" in exc_info.value.detail

    def test_prod_mode_empty_env_variable_raises_500(self, prod_config: AppConfig):
        """In production mode, if APP_API_KEY is empty string, raises HTTPException(500)."""
        with patch.dict(os.environ, {"APP_API_KEY": ""}):
            with pytest.raises(HTTPException) as exc_info:
                get_current_api_key(api_key=None, config=prod_config)
            assert exc_info.value.status_code == 500

    def test_prod_mode_empty_string_key_raises_401(self, prod_config: AppConfig):
        """In production mode, empty string API key raises HTTPException(401)."""
        with patch.dict(os.environ, {"APP_API_KEY": "correct-key"}):
            with pytest.raises(HTTPException) as exc_info:
                get_current_api_key(api_key="", config=prod_config)
            assert exc_info.value.status_code == 401

    def test_prod_mode_whitespace_only_key_raises_401(self, prod_config: AppConfig):
        """In production mode, whitespace-only API key raises HTTPException(401)."""
        with patch.dict(os.environ, {"APP_API_KEY": "correct-key"}):
            with pytest.raises(HTTPException) as exc_info:
                get_current_api_key(api_key="   ", config=prod_config)
            assert exc_info.value.status_code == 401

    def test_prod_mode_very_long_key_accepted(self, prod_config: AppConfig):
        """In production mode, very long API key string is accepted if correct."""
        long_key = "x" * 1000
        with patch.dict(os.environ, {"APP_API_KEY": long_key}):
            result = get_current_api_key(api_key=long_key, config=prod_config)
        assert result == long_key


# ---------------------------------------------------------------------------
# FastAPI integration tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAuthMiddlewareIntegration:
    """Test authentication middleware integration with FastAPI TestClient."""

    def test_dev_mode_health_endpoint_no_auth(self):
        """In dev mode, /api/health endpoint works without authentication."""
        mock_session = _make_mock_session()
        mock_session.run = AsyncMock(side_effect=Exception("no db"))

        dev_config = AppConfig(env="development", neo4j=Neo4jConfig(uri="bolt://mock:7687"))

        with patch("kg.api.app.get_config", return_value=dev_config), patch(
            "kg.api.app.set_config"
        ):
            app = create_app(config=dev_config)

        async def _override_session():
            yield mock_session

        app.dependency_overrides[get_async_neo4j_session] = _override_session
        app.dependency_overrides[get_app_config] = lambda: dev_config

        client = TestClient(app)
        resp = client.get("/api/health")

        assert resp.status_code == 200
        assert resp.json()["status"] == "degraded"

    def test_prod_mode_schema_endpoint_without_key_returns_401(self):
        """In production mode, /api/schema without X-API-Key returns 401."""
        mock_session = _make_mock_session()
        prod_config = AppConfig(env="production", neo4j=Neo4jConfig(uri="bolt://mock:7687"))

        with patch("kg.api.app.get_config", return_value=prod_config), patch(
            "kg.api.app.set_config"
        ):
            app = create_app(config=prod_config)

        async def _override_session():
            yield mock_session

        app.dependency_overrides[get_async_neo4j_session] = _override_session
        app.dependency_overrides[get_app_config] = lambda: prod_config

        with patch.dict(os.environ, {"APP_API_KEY": "test-secret-key"}):
            client = TestClient(app)
            resp = client.get("/api/schema")

        assert resp.status_code == 401

    def test_prod_mode_schema_endpoint_with_correct_key_returns_200(self):
        """In production mode, /api/schema with correct X-API-Key returns 200."""
        mock_session = _make_mock_session()

        # Mock the three session.run calls for schema endpoint
        mock_labels_result = _make_async_mock_result(records=[])
        mock_rel_result = _make_async_mock_result(records=[])
        mock_cnt_record = MagicMock()
        mock_cnt_record.__getitem__ = lambda self, key: 0 if key == "cnt" else None
        mock_cnt_result = _make_async_mock_result(single_value=mock_cnt_record)
        mock_session.run = AsyncMock(
            side_effect=[mock_labels_result, mock_rel_result, mock_cnt_result]
        )

        prod_config = AppConfig(env="production", neo4j=Neo4jConfig(uri="bolt://mock:7687"))

        with patch("kg.api.app.get_config", return_value=prod_config), patch(
            "kg.api.app.set_config"
        ):
            app = create_app(config=prod_config)

        async def _override_session():
            yield mock_session

        app.dependency_overrides[get_async_neo4j_session] = _override_session
        app.dependency_overrides[get_app_config] = lambda: prod_config

        with patch.dict(os.environ, {"APP_API_KEY": "test-secret-key"}):
            client = TestClient(app)
            resp = client.get("/api/schema", headers={"X-API-Key": "test-secret-key"})

        assert resp.status_code == 200
        assert "labels" in resp.json()

    def test_header_name_is_x_api_key(self):
        """Verify that the authentication header name is X-API-Key."""
        mock_session = _make_mock_session()

        mock_labels_result = _make_async_mock_result(records=[])
        mock_rel_result = _make_async_mock_result(records=[])
        mock_cnt_record = MagicMock()
        mock_cnt_record.__getitem__ = lambda self, key: 0 if key == "cnt" else None
        mock_cnt_result = _make_async_mock_result(single_value=mock_cnt_record)
        mock_session.run = AsyncMock(
            side_effect=[mock_labels_result, mock_rel_result, mock_cnt_result]
        )

        prod_config = AppConfig(env="production", neo4j=Neo4jConfig(uri="bolt://mock:7687"))

        with patch("kg.api.app.get_config", return_value=prod_config), patch(
            "kg.api.app.set_config"
        ):
            app = create_app(config=prod_config)

        async def _override_session():
            yield mock_session

        app.dependency_overrides[get_async_neo4j_session] = _override_session
        app.dependency_overrides[get_app_config] = lambda: prod_config

        with patch.dict(os.environ, {"APP_API_KEY": "test-key"}):
            client = TestClient(app)
            # Correct header name
            resp = client.get("/api/schema", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200

    def test_prod_mode_wrong_header_name_returns_401(self):
        """In production mode, using wrong header name (Authorization) returns 401."""
        mock_session = _make_mock_session()
        prod_config = AppConfig(env="production", neo4j=Neo4jConfig(uri="bolt://mock:7687"))

        with patch("kg.api.app.get_config", return_value=prod_config), patch(
            "kg.api.app.set_config"
        ):
            app = create_app(config=prod_config)

        async def _override_session():
            yield mock_session

        app.dependency_overrides[get_async_neo4j_session] = _override_session
        app.dependency_overrides[get_app_config] = lambda: prod_config

        with patch.dict(os.environ, {"APP_API_KEY": "test-key"}):
            client = TestClient(app)
            # Wrong header name: Authorization instead of X-API-Key
            resp = client.get("/api/schema", headers={"Authorization": "test-key"})

        assert resp.status_code == 401

    def test_prod_mode_case_sensitive_key_comparison(self):
        """In production mode, API key comparison is case-sensitive."""
        mock_session = _make_mock_session()
        prod_config = AppConfig(env="production", neo4j=Neo4jConfig(uri="bolt://mock:7687"))

        with patch("kg.api.app.get_config", return_value=prod_config), patch(
            "kg.api.app.set_config"
        ):
            app = create_app(config=prod_config)

        async def _override_session():
            yield mock_session

        app.dependency_overrides[get_async_neo4j_session] = _override_session
        app.dependency_overrides[get_app_config] = lambda: prod_config

        with patch.dict(os.environ, {"APP_API_KEY": "SecretKey123"}):
            client = TestClient(app)
            # Wrong case: secretkey123
            resp = client.get("/api/schema", headers={"X-API-Key": "secretkey123"})

        assert resp.status_code == 401

    def test_prod_mode_special_characters_in_key(self):
        """In production mode, API key can contain special characters."""
        mock_session = _make_mock_session()

        mock_labels_result = _make_async_mock_result(records=[])
        mock_rel_result = _make_async_mock_result(records=[])
        mock_cnt_record = MagicMock()
        mock_cnt_record.__getitem__ = lambda self, key: 0 if key == "cnt" else None
        mock_cnt_result = _make_async_mock_result(single_value=mock_cnt_record)
        mock_session.run = AsyncMock(
            side_effect=[mock_labels_result, mock_rel_result, mock_cnt_result]
        )

        prod_config = AppConfig(env="production", neo4j=Neo4jConfig(uri="bolt://mock:7687"))

        with patch("kg.api.app.get_config", return_value=prod_config), patch(
            "kg.api.app.set_config"
        ):
            app = create_app(config=prod_config)

        async def _override_session():
            yield mock_session

        app.dependency_overrides[get_async_neo4j_session] = _override_session
        app.dependency_overrides[get_app_config] = lambda: prod_config

        special_key = "my-key!@#$%^&*()_+-=[]{}|;':,.<>?/~`"
        with patch.dict(os.environ, {"APP_API_KEY": special_key}):
            client = TestClient(app)
            resp = client.get("/api/schema", headers={"X-API-Key": special_key})

        assert resp.status_code == 200

    def test_prod_mode_health_endpoint_no_auth_required(self):
        """In production mode, /api/health endpoint works without authentication."""
        mock_session = _make_mock_session()
        mock_session.run = AsyncMock(side_effect=Exception("no db"))

        prod_config = AppConfig(env="production", neo4j=Neo4jConfig(uri="bolt://mock:7687"))

        with patch("kg.api.app.get_config", return_value=prod_config), patch(
            "kg.api.app.set_config"
        ):
            app = create_app(config=prod_config)

        async def _override_session():
            yield mock_session

        app.dependency_overrides[get_async_neo4j_session] = _override_session
        app.dependency_overrides[get_app_config] = lambda: prod_config

        with patch.dict(os.environ, {"APP_API_KEY": "test-key"}):
            client = TestClient(app)
            resp = client.get("/api/health")

        # Health endpoint should work without auth even in production
        assert resp.status_code == 200
        assert resp.json()["status"] == "degraded"
