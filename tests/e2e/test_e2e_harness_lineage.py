"""E2E harness tests for lineage exploration endpoints.

Covers /api/v1/lineage/{type}/{id}, /ancestors, /descendants, /timeline.
Uses MockNeo4jSession -- no real Neo4j instance required.
"""
from __future__ import annotations

from typing import Any

import pytest

from tests.helpers.mock_neo4j import (
    MockNeo4jSession,
    MockNeo4jResult,
)
from tests.e2e.conftest import _reset

pytestmark = [
    pytest.mark.unit,
    pytest.mark.asyncio,
]


# ---------------------------------------------------------------------------
# Helpers: build lineage records as plain dicts
# ---------------------------------------------------------------------------


def _lineage_node_record(
    node_id: str,
    entity_type: str,
    entity_id: str,
    created_at: str = "2026-01-15T09:00:00Z",
    edges: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a dict record matching GET_FULL_LINEAGE RETURN columns."""
    return {
        "nodeId": node_id,
        "entityType": entity_type,
        "entityId": entity_id,
        "createdAt": created_at,
        "edges": edges or [],
    }


def _ancestor_record(
    node_id: str,
    entity_type: str,
    entity_id: str,
    depth: int,
    created_at: str = "2026-01-10T08:00:00Z",
) -> dict[str, Any]:
    """Build a dict record matching GET_ANCESTORS RETURN columns."""
    return {
        "nodeId": node_id,
        "entityType": entity_type,
        "entityId": entity_id,
        "createdAt": created_at,
        "depth": depth,
    }


def _descendant_record(
    node_id: str,
    entity_type: str,
    entity_id: str,
    depth: int,
    created_at: str = "2026-02-01T10:00:00Z",
) -> dict[str, Any]:
    """Build a dict record matching GET_DESCENDANTS RETURN columns."""
    return {
        "nodeId": node_id,
        "entityType": entity_type,
        "entityId": entity_id,
        "createdAt": created_at,
        "depth": depth,
    }


def _timeline_event(
    edge_id: str,
    event_type: str,
    agent: str,
    activity: str,
    timestamp: str,
    related_entity_id: str,
    related_entity_type: str,
) -> dict[str, Any]:
    """Build a dict record matching GET_LINEAGE_TIMELINE RETURN columns."""
    return {
        "edgeId": edge_id,
        "eventType": event_type,
        "agent": agent,
        "activity": activity,
        "timestamp": timestamp,
        "relatedEntityId": related_entity_id,
        "relatedEntityType": related_entity_type,
    }


# ===========================================================================
# TestFullLineageHarness
# ===========================================================================


class TestFullLineageHarness:
    """Tests for GET /api/v1/lineage/{entity_type}/{entity_id}."""

    async def test_full_lineage(self, harness: Any) -> None:
        """Two lineage nodes with edges return correct structure."""
        client, session, _app = harness

        records = [
            _lineage_node_record(
                "ln-001", "Vessel", "VES-001",
                edges=[
                    {"edgeId": "e-001", "targetId": "ln-002", "eventType": "DERIVED_FROM",
                     "agent": "crawler", "activity": "import", "timestamp": "2026-01-15T09:00:00Z"},
                ],
            ),
            _lineage_node_record(
                "ln-002", "Document", "DOC-001",
                edges=[],
            ),
        ]
        _reset(session, [MockNeo4jResult(records)])

        resp = await client.get("/api/v1/lineage/Vessel/VES-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["entityType"] == "Vessel"
        assert body["meta"]["entityId"] == "VES-001"
        assert body["meta"]["nodeCount"] == 2
        assert body["meta"]["edgeCount"] >= 1
        assert len(body["nodes"]) == 2
        assert any(n["entityId"] == "VES-001" for n in body["nodes"])

    async def test_full_lineage_empty(self, harness: Any) -> None:
        """No lineage records returns empty lists."""
        client, session, _app = harness

        _reset(session, [MockNeo4jResult([])])

        resp = await client.get("/api/v1/lineage/Vessel/VES-NONE")
        assert resp.status_code == 200
        body = resp.json()
        assert body["nodes"] == []
        assert body["edges"] == []
        assert body["meta"]["nodeCount"] == 0
        assert body["meta"]["edgeCount"] == 0


# ===========================================================================
# TestAncestorsHarness
# ===========================================================================


class TestAncestorsHarness:
    """Tests for GET /api/v1/lineage/{type}/{id}/ancestors."""

    async def test_ancestors(self, harness: Any) -> None:
        """Two ancestor records return correct direction and depth."""
        client, session, _app = harness

        records = [
            _ancestor_record("ln-010", "Document", "DOC-010", depth=1),
            _ancestor_record("ln-011", "Experiment", "EXP-005", depth=2),
        ]
        _reset(session, [MockNeo4jResult(records)])

        resp = await client.get("/api/v1/lineage/Vessel/VES-002/ancestors")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["direction"] == "ancestors"
        assert body["meta"]["count"] == 2
        assert len(body["nodes"]) == 2
        depths = [n["depth"] for n in body["nodes"]]
        assert 1 in depths
        assert 2 in depths

    async def test_ancestors_empty(self, harness: Any) -> None:
        """No ancestors returns empty list."""
        client, session, _app = harness

        _reset(session, [MockNeo4jResult([])])

        resp = await client.get("/api/v1/lineage/Vessel/VES-NOPARENT/ancestors")
        assert resp.status_code == 200
        body = resp.json()
        assert body["nodes"] == []
        assert body["meta"]["count"] == 0


# ===========================================================================
# TestDescendantsHarness
# ===========================================================================


class TestDescendantsHarness:
    """Tests for GET /api/v1/lineage/{type}/{id}/descendants."""

    async def test_descendants(self, harness: Any) -> None:
        """Descendant records return correct direction and depth."""
        client, session, _app = harness

        records = [
            _descendant_record("ln-020", "Regulation", "REG-001", depth=1),
            _descendant_record("ln-021", "Incident", "INC-003", depth=2),
        ]
        _reset(session, [MockNeo4jResult(records)])

        resp = await client.get("/api/v1/lineage/Document/DOC-005/descendants")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["direction"] == "descendants"
        assert body["meta"]["count"] == 2
        assert len(body["nodes"]) == 2

    async def test_descendants_empty(self, harness: Any) -> None:
        """No descendants returns empty list."""
        client, session, _app = harness

        _reset(session, [MockNeo4jResult([])])

        resp = await client.get("/api/v1/lineage/Document/DOC-LEAF/descendants")
        assert resp.status_code == 200
        body = resp.json()
        assert body["nodes"] == []
        assert body["meta"]["count"] == 0


# ===========================================================================
# TestTimelineHarness
# ===========================================================================


class TestTimelineHarness:
    """Tests for GET /api/v1/lineage/{type}/{id}/timeline."""

    async def test_timeline(self, harness: Any) -> None:
        """Three timeline events return correct eventCount."""
        client, session, _app = harness

        records = [
            _timeline_event("e-101", "IMPORT", "crawler-v1", "initial_load",
                            "2026-01-01T00:00:00Z", "DOC-100", "Document"),
            _timeline_event("e-102", "TRANSFORM", "etl-pipeline", "normalize",
                            "2026-01-02T00:00:00Z", "DOC-101", "Document"),
            _timeline_event("e-103", "VALIDATE", "qa-bot", "quality_check",
                            "2026-01-03T00:00:00Z", "REG-050", "Regulation"),
        ]
        _reset(session, [MockNeo4jResult(records)])

        resp = await client.get("/api/v1/lineage/Vessel/VES-TL/timeline")
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["eventCount"] == 3
        assert len(body["events"]) == 3
        event_types = [e["eventType"] for e in body["events"]]
        assert "IMPORT" in event_types
        assert "TRANSFORM" in event_types
        assert "VALIDATE" in event_types

    async def test_timeline_empty(self, harness: Any) -> None:
        """No timeline events returns empty list."""
        client, session, _app = harness

        _reset(session, [MockNeo4jResult([])])

        resp = await client.get("/api/v1/lineage/Vessel/VES-NOTL/timeline")
        assert resp.status_code == 200
        body = resp.json()
        assert body["events"] == []
        assert body["meta"]["eventCount"] == 0
