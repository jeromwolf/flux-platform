"""Unit tests for the Maritime KG FastAPI application.

All Neo4j interactions are mocked so these tests run without a database.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from kg.api.app import create_app
from kg.api.deps import get_app_config, get_async_neo4j_session
from maritime.entity_groups import (
    ENTITY_GROUPS,
    GROUP_COLORS,
    get_color_for_label,
    get_group_for_label,
)
from kg.api.middleware.auth import get_current_api_key
from kg.api.models import (
    EdgeResponse,
    ErrorResponse,
    GraphResponse,
    HealthResponse,
    NodeResponse,
    SchemaLabelInfo,
    SchemaResponse,
)
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


_DEV_CONFIG = AppConfig(
    env="development",
    neo4j=Neo4jConfig(uri="bolt://mock:7687"),
)


def _make_async_mock_result(records: list | None = None, single_value: Any = None) -> MagicMock:
    """Create a mock async result that supports ``async for`` and ``await .single()``.

    Args:
        records: List of records for async iteration. Defaults to empty.
        single_value: Return value for ``await result.single()``.
    """
    mock_result = MagicMock()
    _records = records if records is not None else []

    async def _aiter_impl():
        for r in _records:
            yield r

    mock_result.__aiter__ = lambda self: _aiter_impl()
    mock_result.single = AsyncMock(return_value=single_value)
    return mock_result


# We still need a type annotation import for the helper
from typing import Any  # noqa: E402


def _make_mock_session() -> MagicMock:
    """Create a mock async Neo4j session.

    The mock has:
    - ``run()`` as AsyncMock
    - ``close()`` as AsyncMock
    """
    mock_session = MagicMock()
    mock_session.run = AsyncMock()
    mock_session.close = AsyncMock()
    return mock_session


def _make_client(mock_session: MagicMock | None = None) -> tuple[TestClient, MagicMock]:
    """Create a TestClient with FastAPI dependency overrides for Neo4j."""
    if mock_session is None:
        mock_session = _make_mock_session()

    # Prevent create_app from initializing a real Neo4j driver
    with patch("kg.api.app.get_config", return_value=_DEV_CONFIG), patch("kg.api.app.set_config"):
        app = create_app(config=_DEV_CONFIG)

    # Override dependencies at the FastAPI level so no real driver is used
    async def _override_session():
        yield mock_session

    app.dependency_overrides[get_async_neo4j_session] = _override_session
    app.dependency_overrides[get_app_config] = lambda: _DEV_CONFIG
    app.dependency_overrides[get_current_api_key] = lambda: None

    return TestClient(app), mock_session


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHealthEndpoint:
    def test_health_endpoint_returns_ok(self):
        """Health returns 'ok' when Neo4j is reachable."""
        mock_session = _make_mock_session()
        mock_record = MagicMock()
        mock_record.__getitem__ = lambda self, key: 1 if key == "n" else None
        mock_result = _make_async_mock_result(single_value=mock_record)
        mock_session.run = AsyncMock(return_value=mock_result)

        client, _ = _make_client(mock_session)
        resp = client.get("/api/v1/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["neo4j_connected"] is True
        assert data["version"] == "0.1.0"

    def test_health_endpoint_structure(self):
        """Health response contains all expected fields."""
        mock_session = _make_mock_session()
        mock_session.run = AsyncMock(side_effect=Exception("connection refused"))

        client, _ = _make_client(mock_session)
        resp = client.get("/api/v1/health")

        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "version" in data
        assert "neo4j_connected" in data
        assert data["status"] == "degraded"
        assert data["neo4j_connected"] is False


# ---------------------------------------------------------------------------
# Graph endpoints
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSubgraphEndpoint:
    def test_subgraph_endpoint_requires_valid_label(self):
        """Subgraph with a valid alphanumeric label does not error."""
        mock_session = _make_mock_session()
        mock_result = _make_async_mock_result(records=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        client, _ = _make_client(mock_session)
        resp = client.get("/api/v1/subgraph", params={"label": "Vessel", "limit": 10})

        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert "meta" in data
        assert data["meta"]["label"] == "Vessel"

    def test_subgraph_endpoint_rejects_invalid_label(self):
        """Subgraph with non-alphanumeric label returns error in meta."""
        client, _ = _make_client()
        resp = client.get("/api/v1/subgraph", params={"label": "DROP; --"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["nodes"] == []
        assert data["edges"] == []
        assert "error" in data["meta"]


@pytest.mark.unit
class TestNeighborsEndpoint:
    def test_neighbors_endpoint_requires_node_id(self):
        """Neighbors endpoint requires nodeId query parameter."""
        client, _ = _make_client()
        resp = client.get("/api/v1/neighbors")

        # FastAPI returns 422 for missing required query params
        assert resp.status_code == 422


@pytest.mark.unit
class TestSearchEndpoint:
    def test_search_endpoint_requires_query(self):
        """Search endpoint requires q query parameter."""
        client, _ = _make_client()
        resp = client.get("/api/v1/search")

        assert resp.status_code == 422

    def test_search_endpoint_rejects_empty_query(self):
        """Search endpoint rejects empty string for q."""
        client, _ = _make_client()
        resp = client.get("/api/v1/search", params={"q": ""})

        # FastAPI min_length=1 validation returns 422
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Schema endpoint
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSchemaEndpoint:
    def test_schema_endpoint_returns_structure(self):
        """Schema endpoint returns expected top-level keys."""
        mock_session = _make_mock_session()

        # Mock labels result
        mock_label_record = MagicMock()
        mock_label_record.__getitem__ = lambda self, key: "Vessel" if key == "label" else None
        mock_labels_result = _make_async_mock_result(records=[mock_label_record])

        # Mock rel types result
        mock_rel_record = MagicMock()
        mock_rel_record.__getitem__ = lambda self, key: (
            "DOCKED_AT" if key == "relationshipType" else None
        )
        mock_rel_result = _make_async_mock_result(records=[mock_rel_record])

        # Mock count result
        mock_cnt_record = MagicMock()
        mock_cnt_record.__getitem__ = lambda self, key: 42 if key == "cnt" else None
        mock_cnt_result = _make_async_mock_result(single_value=mock_cnt_record)

        # session.run returns different results per call
        mock_session.run = AsyncMock(
            side_effect=[mock_labels_result, mock_rel_result, mock_cnt_result]
        )

        client, _ = _make_client(mock_session)
        resp = client.get("/api/v1/schema")

        assert resp.status_code == 200
        data = resp.json()
        assert "labels" in data
        assert "relationshipTypes" in data
        assert "entityGroups" in data
        assert "totalLabels" in data
        assert "totalRelationshipTypes" in data
        assert data["totalLabels"] == 1
        assert data["totalRelationshipTypes"] == 1


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCORS:
    def test_cors_headers_present(self):
        """CORS headers are included in responses."""
        mock_session = _make_mock_session()
        mock_session.run = AsyncMock(side_effect=Exception("no db"))

        client, _ = _make_client(mock_session)
        resp = client.get(
            "/api/v1/health",
            headers={"Origin": "http://localhost:3000"},
        )

        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers


# ---------------------------------------------------------------------------
# Entity groups module
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEntityGroupsModule:
    def test_entity_groups_module(self):
        """Entity groups module provides expected API."""
        assert isinstance(ENTITY_GROUPS, dict)
        assert isinstance(GROUP_COLORS, dict)
        assert len(ENTITY_GROUPS) > 0
        assert len(GROUP_COLORS) > 0

        # All groups in GROUP_COLORS should be in ENTITY_GROUPS
        for group in GROUP_COLORS:
            assert group in ENTITY_GROUPS

        # Known labels map correctly
        assert get_group_for_label("Vessel") == "PhysicalEntity"
        assert get_group_for_label("Port") == "PhysicalEntity"
        assert get_group_for_label("Voyage") == "TemporalEntity"
        assert get_group_for_label("NonExistent") == "Unknown"

        # Colors
        assert get_color_for_label("Vessel") == "#4A90D9"
        assert get_color_for_label("NonExistent") == "#888888"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPydanticModels:
    def test_pydantic_models_validation(self):
        """Pydantic models accept valid data and enforce types."""
        node = NodeResponse(
            id="4:abc:0",
            labels=["Vessel"],
            primaryLabel="Vessel",
            group="PhysicalEntity",
            color="#4A90D9",
            properties={"name": "Test Ship"},
            displayName="Test Ship",
        )
        assert node.id == "4:abc:0"
        assert node.primaryLabel == "Vessel"

        edge = EdgeResponse(
            id="5:abc:0",
            type="DOCKED_AT",
            sourceId="4:abc:0",
            targetId="4:abc:1",
            properties={},
        )
        assert edge.type == "DOCKED_AT"

        graph = GraphResponse(nodes=[node], edges=[edge], meta={"count": 1})
        assert len(graph.nodes) == 1
        assert len(graph.edges) == 1

        health = HealthResponse(status="ok", version="0.1.0", neo4j_connected=True)
        assert health.status == "ok"

        schema_label = SchemaLabelInfo(
            label="Vessel", group="PhysicalEntity", color="#4A90D9", count=10
        )
        assert schema_label.count == 10

        schema_resp = SchemaResponse(
            labels=[schema_label],
            relationshipTypes=["DOCKED_AT"],
            entityGroups={},
            totalLabels=1,
            totalRelationshipTypes=1,
        )
        assert schema_resp.totalLabels == 1

        error = ErrorResponse(error="not found", detail="Node does not exist")
        assert error.error == "not found"


# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAuthMiddleware:
    def test_auth_skipped_in_dev_mode(self):
        """Auth is skipped when config.env == 'development'."""
        mock_session = _make_mock_session()
        mock_session.run = AsyncMock(side_effect=Exception("no db"))

        client, _ = _make_client(mock_session)

        # Request without API key should succeed in dev mode
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Auth middleware - Production mode
# ---------------------------------------------------------------------------

_PROD_CONFIG = AppConfig(
    env="production",
    neo4j=Neo4jConfig(uri="bolt://mock:7687"),
)


def _make_prod_client(mock_session: MagicMock | None = None) -> TestClient:
    """Create a TestClient configured for production mode (auth enforced).

    Unlike ``_make_client`` this does NOT override ``get_current_api_key``,
    so the real auth middleware runs.
    """
    if mock_session is None:
        mock_session = _make_mock_session()

    with patch("kg.api.app.get_config", return_value=_PROD_CONFIG), patch("kg.api.app.set_config"):
        app = create_app(config=_PROD_CONFIG)

    async def _override_session():
        yield mock_session

    app.dependency_overrides[get_async_neo4j_session] = _override_session
    app.dependency_overrides[get_app_config] = lambda: _PROD_CONFIG
    # NOTE: get_current_api_key is NOT overridden so the real middleware runs.

    return TestClient(app)


@pytest.mark.unit
class TestAuthProduction:
    """Test API key authentication in production mode."""

    def test_auth_required_in_production_mode(self):
        """Request without X-API-Key header returns 401 in production."""
        with patch.dict(os.environ, {"APP_API_KEY": "test-secret-key"}):
            client = _make_prod_client()
            resp = client.get("/api/v1/schema")
        assert resp.status_code == 401

    def test_auth_valid_key_in_production(self):
        """Request with correct X-API-Key succeeds in production."""
        mock_session = _make_mock_session()

        # Mock the schema endpoint's three session.run calls
        mock_labels_result = _make_async_mock_result(records=[])
        mock_rel_result = _make_async_mock_result(records=[])
        mock_cnt_record = MagicMock()
        mock_cnt_record.__getitem__ = lambda self, key: 0 if key == "cnt" else None
        mock_cnt_result = _make_async_mock_result(single_value=mock_cnt_record)
        mock_session.run = AsyncMock(
            side_effect=[mock_labels_result, mock_rel_result, mock_cnt_result]
        )

        with patch.dict(os.environ, {"APP_API_KEY": "test-secret-key"}):
            client = _make_prod_client(mock_session)
            resp = client.get("/api/v1/schema", headers={"X-API-Key": "test-secret-key"})
        assert resp.status_code == 200

    def test_auth_invalid_key_in_production(self):
        """Request with wrong X-API-Key returns 401 in production."""
        with patch.dict(os.environ, {"APP_API_KEY": "test-secret-key"}):
            client = _make_prod_client()
            resp = client.get("/api/v1/schema", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401

    def test_health_no_auth_required(self):
        """Health endpoint works without API key even in production."""
        mock_session = _make_mock_session()
        mock_session.run = AsyncMock(side_effect=Exception("no db"))

        with patch.dict(os.environ, {"APP_API_KEY": "test-secret-key"}):
            client = _make_prod_client(mock_session)
            resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "degraded"
