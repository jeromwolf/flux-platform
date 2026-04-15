"""Unit tests for RBAC route-level access control.

Tests verify that ``require_role`` correctly enforces role-based access on
the three dependency tiers (viewer+, writer, admin) defined in ``app.py``.

- Development mode: all roles pass (``get_current_user`` returns admin).
- Production mode: role enforcement is strict.
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
from kg.api.middleware.auth import get_current_user, require_role
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
    return AppConfig(env="development", neo4j=Neo4jConfig(uri="bolt://mock:7687"))


@pytest.fixture
def prod_config() -> AppConfig:
    return AppConfig(env="production", neo4j=Neo4jConfig(uri="bolt://mock:7687"))


def _make_mock_session() -> MagicMock:
    """Create a mock async Neo4j session."""
    mock = MagicMock()
    mock.run = AsyncMock()
    mock.close = AsyncMock()
    return mock


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


def _create_test_app(cfg: AppConfig) -> TestClient:
    """Create a TestClient with mocked Neo4j and config."""
    mock_session = _make_mock_session()
    # Provide minimal mock results to avoid errors on read routes
    mock_labels_result = _make_async_mock_result(records=[])
    mock_rel_result = _make_async_mock_result(records=[])
    mock_cnt_record = MagicMock()
    mock_cnt_record.__getitem__ = lambda self, key: 0 if key == "cnt" else None
    mock_cnt_result = _make_async_mock_result(single_value=mock_cnt_record)
    mock_session.run = AsyncMock(
        side_effect=[mock_labels_result, mock_rel_result, mock_cnt_result]
    )

    with patch("kg.api.app.get_config", return_value=cfg), patch("kg.api.app.set_config"):
        app = create_app(config=cfg)

    async def _override_session():
        yield mock_session

    app.dependency_overrides[get_async_neo4j_session] = _override_session
    app.dependency_overrides[get_app_config] = lambda: cfg

    return app, TestClient(app)


def _override_user(app, *, role: str = "viewer", roles: list[str] | None = None):
    """Override get_current_user to return a user with the given role."""
    roles = roles if roles is not None else []
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "test-user",
        "role": role,
        "roles": roles,
        "auth_method": "test",
    }


# ---------------------------------------------------------------------------
# require_role unit tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRequireRoleFactory:
    """Tests for the require_role dependency factory (unit level)."""

    @pytest.mark.asyncio
    async def test_matching_primary_role_passes(self):
        """User with matching primary role is allowed."""
        checker = require_role("admin")
        user = {"sub": "u1", "role": "admin", "roles": []}
        result = await checker(user=user)
        assert result["sub"] == "u1"

    @pytest.mark.asyncio
    async def test_matching_realm_role_passes(self):
        """User with matching role in ``roles`` list is allowed."""
        checker = require_role("researcher")
        user = {"sub": "u2", "role": "viewer", "roles": ["researcher"]}
        result = await checker(user=user)
        assert result["sub"] == "u2"

    @pytest.mark.asyncio
    async def test_no_matching_role_raises_403(self):
        """User without any matching role gets 403."""
        checker = require_role("admin")
        user = {"sub": "u3", "role": "viewer", "roles": []}
        with pytest.raises(HTTPException) as exc_info:
            await checker(user=user)
        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_multiple_allowed_roles(self):
        """Any of the allowed roles is accepted."""
        checker = require_role("researcher", "developer", "admin")
        user = {"sub": "u4", "role": "developer", "roles": []}
        result = await checker(user=user)
        assert result["sub"] == "u4"

    @pytest.mark.asyncio
    async def test_empty_user_role_raises_403(self):
        """Empty role string should not match."""
        checker = require_role("admin")
        user = {"sub": "u5", "role": "", "roles": []}
        with pytest.raises(HTTPException) as exc_info:
            await checker(user=user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_role_in_both_primary_and_list(self):
        """Duplicate roles in primary and list should still pass."""
        checker = require_role("admin")
        user = {"sub": "u6", "role": "admin", "roles": ["admin"]}
        result = await checker(user=user)
        assert result["sub"] == "u6"

    @pytest.mark.asyncio
    async def test_detail_message_lists_required_roles(self):
        """Error detail should list all required roles."""
        checker = require_role("researcher", "admin")
        user = {"sub": "u7", "role": "viewer", "roles": []}
        with pytest.raises(HTTPException) as exc_info:
            await checker(user=user)
        detail = exc_info.value.detail
        assert "researcher" in detail
        assert "admin" in detail


# ---------------------------------------------------------------------------
# Development mode integration tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRBACDevMode:
    """In development mode, all routes should be accessible (admin bypass)."""

    def test_dev_mode_read_route_accessible(self, dev_config: AppConfig):
        """Read route (schema) accessible in dev mode without explicit auth."""
        app, client = _create_test_app(dev_config)
        resp = client.get("/api/v1/schema")
        assert resp.status_code == 200

    def test_dev_mode_write_route_accessible(self, dev_config: AppConfig):
        """Write route (nodes search) accessible in dev mode."""
        app, client = _create_test_app(dev_config)
        # GET /nodes returns list — mock returns empty
        mock_session = _make_mock_session()
        mock_result = _make_async_mock_result(records=[])
        mock_count_rec = MagicMock()
        mock_count_rec.__getitem__ = lambda self, key: 0 if key == "total" else None
        mock_count_result = _make_async_mock_result(single_value=mock_count_rec)
        mock_session.run = AsyncMock(side_effect=[mock_result, mock_count_result])

        async def _s():
            yield mock_session

        app.dependency_overrides[get_async_neo4j_session] = _s
        client2 = TestClient(app)
        resp = client2.get("/api/v1/nodes")
        assert resp.status_code == 200

    def test_dev_mode_admin_route_accessible(self, dev_config: AppConfig):
        """Admin route (cypher validate) accessible in dev mode."""
        app, client = _create_test_app(dev_config)
        resp = client.post(
            "/api/v1/cypher/validate",
            json={"query": "MATCH (n) RETURN n LIMIT 1"},
        )
        # Should not be 403 — could be 200 or another status depending on handler
        assert resp.status_code != 403


# ---------------------------------------------------------------------------
# Production mode RBAC enforcement tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRBACProdModeViewer:
    """Viewer role in production mode — read-only access."""

    def test_viewer_can_access_read_route(self, prod_config: AppConfig):
        """Viewer can access schema (read-only)."""
        app, client = _create_test_app(prod_config)
        _override_user(app, role="viewer")
        resp = client.get("/api/v1/schema")
        assert resp.status_code == 200

    def test_viewer_blocked_from_write_route(self, prod_config: AppConfig):
        """Viewer cannot access nodes (write route) — 403."""
        app, client = _create_test_app(prod_config)
        _override_user(app, role="viewer")
        resp = client.get("/api/v1/nodes")
        assert resp.status_code == 403

    def test_viewer_blocked_from_admin_route(self, prod_config: AppConfig):
        """Viewer cannot access cypher (admin route) — 403."""
        app, client = _create_test_app(prod_config)
        _override_user(app, role="viewer")
        resp = client.post(
            "/api/v1/cypher/validate",
            json={"query": "MATCH (n) RETURN n LIMIT 1"},
        )
        assert resp.status_code == 403


@pytest.mark.unit
class TestRBACProdModeResearcher:
    """Researcher role in production mode — read + write access."""

    def test_researcher_can_access_read_route(self, prod_config: AppConfig):
        """Researcher can access schema."""
        app, client = _create_test_app(prod_config)
        _override_user(app, role="researcher")
        resp = client.get("/api/v1/schema")
        assert resp.status_code == 200

    def test_researcher_can_access_write_route(self, prod_config: AppConfig):
        """Researcher can access nodes (write route)."""
        app, client = _create_test_app(prod_config)
        _override_user(app, role="researcher")
        mock_session = _make_mock_session()
        mock_result = _make_async_mock_result(records=[])
        mock_count_rec = MagicMock()
        mock_count_rec.__getitem__ = lambda self, key: 0 if key == "total" else None
        mock_count_result = _make_async_mock_result(single_value=mock_count_rec)
        mock_session.run = AsyncMock(side_effect=[mock_result, mock_count_result])

        async def _s():
            yield mock_session

        app.dependency_overrides[get_async_neo4j_session] = _s
        client2 = TestClient(app)
        resp = client2.get("/api/v1/nodes")
        assert resp.status_code == 200

    def test_researcher_blocked_from_admin_route(self, prod_config: AppConfig):
        """Researcher cannot access cypher (admin route) — 403."""
        app, client = _create_test_app(prod_config)
        _override_user(app, role="researcher")
        resp = client.post(
            "/api/v1/cypher/validate",
            json={"query": "MATCH (n) RETURN n LIMIT 1"},
        )
        assert resp.status_code == 403


@pytest.mark.unit
class TestRBACProdModeDeveloper:
    """Developer role in production mode — read + write access, no admin."""

    def test_developer_can_access_read_route(self, prod_config: AppConfig):
        app, client = _create_test_app(prod_config)
        _override_user(app, role="developer")
        resp = client.get("/api/v1/schema")
        assert resp.status_code == 200

    def test_developer_can_access_write_route(self, prod_config: AppConfig):
        app, client = _create_test_app(prod_config)
        _override_user(app, role="developer")
        mock_session = _make_mock_session()
        mock_result = _make_async_mock_result(records=[])
        mock_count_rec = MagicMock()
        mock_count_rec.__getitem__ = lambda self, key: 0 if key == "total" else None
        mock_count_result = _make_async_mock_result(single_value=mock_count_rec)
        mock_session.run = AsyncMock(side_effect=[mock_result, mock_count_result])

        async def _s():
            yield mock_session

        app.dependency_overrides[get_async_neo4j_session] = _s
        client2 = TestClient(app)
        resp = client2.get("/api/v1/nodes")
        assert resp.status_code == 200

    def test_developer_blocked_from_admin_route(self, prod_config: AppConfig):
        app, client = _create_test_app(prod_config)
        _override_user(app, role="developer")
        resp = client.post(
            "/api/v1/cypher/validate",
            json={"query": "MATCH (n) RETURN n LIMIT 1"},
        )
        assert resp.status_code == 403


@pytest.mark.unit
class TestRBACProdModeAdmin:
    """Admin role in production mode — full access."""

    def test_admin_can_access_read_route(self, prod_config: AppConfig):
        app, client = _create_test_app(prod_config)
        _override_user(app, role="admin")
        resp = client.get("/api/v1/schema")
        assert resp.status_code == 200

    def test_admin_can_access_write_route(self, prod_config: AppConfig):
        app, client = _create_test_app(prod_config)
        _override_user(app, role="admin")
        mock_session = _make_mock_session()
        mock_result = _make_async_mock_result(records=[])
        mock_count_rec = MagicMock()
        mock_count_rec.__getitem__ = lambda self, key: 0 if key == "total" else None
        mock_count_result = _make_async_mock_result(single_value=mock_count_rec)
        mock_session.run = AsyncMock(side_effect=[mock_result, mock_count_result])

        async def _s():
            yield mock_session

        app.dependency_overrides[get_async_neo4j_session] = _s
        client2 = TestClient(app)
        resp = client2.get("/api/v1/nodes")
        assert resp.status_code == 200

    def test_admin_can_access_admin_route(self, prod_config: AppConfig):
        app, client = _create_test_app(prod_config)
        _override_user(app, role="admin")
        resp = client.post(
            "/api/v1/cypher/validate",
            json={"query": "MATCH (n) RETURN n LIMIT 1"},
        )
        # Should not be 403 — admin has full access
        assert resp.status_code != 403


@pytest.mark.unit
class TestRBACProdModeNoRole:
    """User with no meaningful role in production mode."""

    def test_no_role_can_access_read_route(self, prod_config: AppConfig):
        """User with unknown role can still access read routes (viewer+)."""
        app, client = _create_test_app(prod_config)
        _override_user(app, role="unknown")
        resp = client.get("/api/v1/schema")
        # Read routes use get_current_user (no role check), so should pass
        assert resp.status_code == 200

    def test_no_role_blocked_from_write_route(self, prod_config: AppConfig):
        """User with unknown role cannot access write routes."""
        app, client = _create_test_app(prod_config)
        _override_user(app, role="unknown")
        resp = client.get("/api/v1/nodes")
        assert resp.status_code == 403

    def test_no_role_blocked_from_admin_route(self, prod_config: AppConfig):
        """User with unknown role cannot access admin routes."""
        app, client = _create_test_app(prod_config)
        _override_user(app, role="unknown")
        resp = client.post(
            "/api/v1/cypher/validate",
            json={"query": "MATCH (n) RETURN n LIMIT 1"},
        )
        assert resp.status_code == 403


@pytest.mark.unit
class TestRBACRealmRoles:
    """Tests for Keycloak realm_access.roles integration."""

    def test_viewer_with_admin_realm_role_gets_admin_access(self, prod_config: AppConfig):
        """Primary role is viewer but realm roles include admin — admin access granted."""
        app, client = _create_test_app(prod_config)
        _override_user(app, role="viewer", roles=["admin"])
        resp = client.post(
            "/api/v1/cypher/validate",
            json={"query": "MATCH (n) RETURN n LIMIT 1"},
        )
        assert resp.status_code != 403

    def test_viewer_with_researcher_realm_role_gets_write_access(self, prod_config: AppConfig):
        """Primary role is viewer but realm roles include researcher — write access granted."""
        app, client = _create_test_app(prod_config)
        _override_user(app, role="viewer", roles=["researcher"])
        mock_session = _make_mock_session()
        mock_result = _make_async_mock_result(records=[])
        mock_count_rec = MagicMock()
        mock_count_rec.__getitem__ = lambda self, key: 0 if key == "total" else None
        mock_count_result = _make_async_mock_result(single_value=mock_count_rec)
        mock_session.run = AsyncMock(side_effect=[mock_result, mock_count_result])

        async def _s():
            yield mock_session

        app.dependency_overrides[get_async_neo4j_session] = _s
        client2 = TestClient(app)
        resp = client2.get("/api/v1/nodes")
        assert resp.status_code == 200

    def test_realm_role_does_not_grant_higher_tier(self, prod_config: AppConfig):
        """Researcher in realm_roles does not grant admin access."""
        app, client = _create_test_app(prod_config)
        _override_user(app, role="viewer", roles=["researcher"])
        resp = client.post(
            "/api/v1/cypher/validate",
            json={"query": "MATCH (n) RETURN n LIMIT 1"},
        )
        assert resp.status_code == 403


@pytest.mark.unit
class TestRBACHealthNoAuth:
    """Health endpoint should never require authentication."""

    def test_health_accessible_without_auth_prod(self, prod_config: AppConfig):
        """Health endpoint works in prod without any auth override."""
        mock_session = _make_mock_session()
        mock_session.run = AsyncMock(side_effect=Exception("no db"))

        with patch("kg.api.app.get_config", return_value=prod_config), patch(
            "kg.api.app.set_config"
        ):
            app = create_app(config=prod_config)

        async def _s():
            yield mock_session

        app.dependency_overrides[get_async_neo4j_session] = _s
        app.dependency_overrides[get_app_config] = lambda: prod_config
        # Override get_current_user to raise 401 — health should still work
        app.dependency_overrides[get_current_user] = lambda: (_ for _ in ()).throw(
            HTTPException(status_code=401, detail="test")
        )

        client = TestClient(app)
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
