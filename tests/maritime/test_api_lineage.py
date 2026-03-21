"""Unit tests for the Lineage API endpoints.

All tests are marked with ``@pytest.mark.unit`` and mock Neo4j so no
database connection is required.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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


_DEV_CONFIG = AppConfig(
    env="development",
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


def _make_client(
    mock_session: MagicMock | None = None,
) -> tuple[TestClient, MagicMock]:
    """Create a TestClient with dependency overrides for Neo4j.

    Returns:
        Tuple of (TestClient, mock_session).
    """
    if mock_session is None:
        mock_session = _make_mock_session()

    with patch("kg.api.app.get_config", return_value=_DEV_CONFIG), patch(
        "kg.api.app.set_config"
    ):
        app = create_app(config=_DEV_CONFIG)

    async def _override_session():
        yield mock_session

    app.dependency_overrides[get_async_neo4j_session] = _override_session
    app.dependency_overrides[get_app_config] = lambda: _DEV_CONFIG
    app.dependency_overrides[get_current_api_key] = lambda: None

    return TestClient(app), mock_session


# ---------------------------------------------------------------------------
# GET /api/lineage/{entity_type}/{entity_id}
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetFullLineage:
    """Test GET /api/lineage/{entity_type}/{entity_id}."""

    def test_returns_empty_lineage_for_unknown_entity(self) -> None:
        """An entity with no lineage returns empty nodes and edges."""
        mock_session = _make_mock_session()
        mock_result = _make_async_mock_result(records=[])
        mock_session.run = AsyncMock(return_value=mock_result)

        client, _ = _make_client(mock_session)
        resp = client.get("/api/v1/lineage/Vessel/VES-001")

        assert resp.status_code == 200
        data = resp.json()
        assert data["nodes"] == []
        assert data["edges"] == []
        assert data["meta"]["entityType"] == "Vessel"
        assert data["meta"]["entityId"] == "VES-001"
        assert data["meta"]["nodeCount"] == 0
        assert data["meta"]["edgeCount"] == 0

    def test_returns_lineage_nodes_and_edges(self) -> None:
        """When lineage exists, nodes and edges are returned."""
        mock_session = _make_mock_session()

        record1 = {
            "nodeId": "ln-001",
            "entityType": "Vessel",
            "entityId": "VES-001",
            "createdAt": "2025-01-01T00:00:00Z",
            "edges": [
                {
                    "edgeId": "edge-001",
                    "targetId": "ln-002",
                    "eventType": "DERIVATION",
                    "agent": "ETL-1",
                    "activity": "Import",
                    "timestamp": "2025-01-01T00:00:00Z",
                }
            ],
        }
        record2 = {
            "nodeId": "ln-002",
            "entityType": "Dataset",
            "entityId": "DS-001",
            "createdAt": "2025-01-02T00:00:00Z",
            "edges": [],
        }

        mock_result = _make_async_mock_result(records=[record1, record2])
        mock_session.run = AsyncMock(return_value=mock_result)

        client, _ = _make_client(mock_session)
        resp = client.get("/api/v1/lineage/Vessel/VES-001")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) == 2
        assert data["nodes"][0]["nodeId"] == "ln-001"
        assert data["nodes"][1]["nodeId"] == "ln-002"
        assert len(data["edges"]) == 1
        assert data["edges"][0]["edgeId"] == "edge-001"
        assert data["meta"]["nodeCount"] == 2
        assert data["meta"]["edgeCount"] == 1


# ---------------------------------------------------------------------------
# GET /api/lineage/{entity_type}/{entity_id}/ancestors
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetAncestors:
    """Test GET /api/lineage/{entity_type}/{entity_id}/ancestors."""

    def test_returns_ancestor_nodes(self) -> None:
        """Ancestor query returns node list with depth information."""
        mock_session = _make_mock_session()

        ancestor = {
            "nodeId": "ln-parent",
            "entityType": "Dataset",
            "entityId": "DS-001",
            "createdAt": "2025-01-01T00:00:00Z",
            "depth": 1,
        }

        mock_result = _make_async_mock_result(records=[ancestor])
        mock_session.run = AsyncMock(return_value=mock_result)

        client, _ = _make_client(mock_session)
        resp = client.get("/api/v1/lineage/Vessel/VES-001/ancestors")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["nodeId"] == "ln-parent"
        assert data["nodes"][0]["depth"] == 1
        assert data["meta"]["direction"] == "ancestors"
        assert data["meta"]["count"] == 1


# ---------------------------------------------------------------------------
# GET /api/lineage/{entity_type}/{entity_id}/descendants
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetDescendants:
    """Test GET /api/lineage/{entity_type}/{entity_id}/descendants."""

    def test_returns_descendant_nodes(self) -> None:
        """Descendant query returns node list with depth information."""
        mock_session = _make_mock_session()

        descendant = {
            "nodeId": "ln-child",
            "entityType": "Report",
            "entityId": "RPT-001",
            "createdAt": "2025-02-01T00:00:00Z",
            "depth": 1,
        }

        mock_result = _make_async_mock_result(records=[descendant])
        mock_session.run = AsyncMock(return_value=mock_result)

        client, _ = _make_client(mock_session)
        resp = client.get("/api/v1/lineage/Vessel/VES-001/descendants")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) == 1
        assert data["nodes"][0]["nodeId"] == "ln-child"
        assert data["nodes"][0]["entityType"] == "Report"
        assert data["meta"]["direction"] == "descendants"
        assert data["meta"]["count"] == 1


# ---------------------------------------------------------------------------
# GET /api/lineage/{entity_type}/{entity_id}/timeline
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetLineageTimeline:
    """Test GET /api/lineage/{entity_type}/{entity_id}/timeline."""

    def test_returns_timeline_events(self) -> None:
        """Timeline query returns chronologically ordered events."""
        mock_session = _make_mock_session()

        event = {
            "edgeId": "edge-001",
            "eventType": "CREATION",
            "agent": "ETL-Pipeline-1",
            "activity": "AIS data import",
            "timestamp": "2025-01-01T00:00:00Z",
            "relatedEntityId": "DS-001",
            "relatedEntityType": "Dataset",
        }

        mock_result = _make_async_mock_result(records=[event])
        mock_session.run = AsyncMock(return_value=mock_result)

        client, _ = _make_client(mock_session)
        resp = client.get("/api/v1/lineage/Vessel/VES-001/timeline")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["edgeId"] == "edge-001"
        assert data["events"][0]["eventType"] == "CREATION"
        assert data["events"][0]["agent"] == "ETL-Pipeline-1"
        assert data["meta"]["entityType"] == "Vessel"
        assert data["meta"]["entityId"] == "VES-001"
        assert data["meta"]["eventCount"] == 1
