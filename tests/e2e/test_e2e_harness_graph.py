"""E2E harness tests for graph exploration endpoints (subgraph, neighbors, search).

Uses MockNeo4jSession -- no real Neo4j instance required.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from tests.helpers.mock_neo4j import (
    MockNeo4jSession,
    MockNeo4jResult,
    FakeNode,
    FakeRelationship,
    make_neo4j_node,
    make_neo4j_relationship,
)
from tests.e2e.conftest import _reset

pytestmark = [
    pytest.mark.unit,
    pytest.mark.asyncio,
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _graph_record(
    n: FakeNode,
    m: FakeNode | None = None,
    r: FakeRelationship | None = None,
) -> dict[str, Any]:
    """Build a dict record with keys ``n``, ``r``, ``m`` as expected by ``_collect_graph``."""
    return {"n": n, "r": r, "m": m}


# ===========================================================================
# TestSubgraphHarness
# ===========================================================================


class TestSubgraphHarness:
    """Tests for GET /api/v1/subgraph."""

    async def test_subgraph_known_label(self, harness: Any) -> None:
        """Known label with mock results returns nodes and edges."""
        client, session, _app = harness

        n1 = make_neo4j_node(element_id="4:g:1", labels=["Vessel", "KG_default"], props={"name": "세종대왕함"})
        n2 = make_neo4j_node(element_id="4:g:2", labels=["Port", "KG_default"], props={"name": "부산항"})
        rel = make_neo4j_relationship(element_id="5:g:1", rel_type="DOCKED_AT", src_id="4:g:1", tgt_id="4:g:2")

        records = [_graph_record(n1, n2, rel)]
        _reset(session, [MockNeo4jResult(records)])

        with patch("kg.api.routes.graph._LABEL_TO_GROUP", {"Vessel": "PhysicalEntity"}):
            resp = await client.get("/api/v1/subgraph", params={"label": "Vessel", "limit": 50})

        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["label"] == "Vessel"
        assert body["meta"]["nodeCount"] >= 1
        assert body["meta"]["edgeCount"] >= 1
        assert len(body["nodes"]) >= 1
        assert len(body["edges"]) >= 1

    async def test_subgraph_unknown_label(self, harness: Any) -> None:
        """Unknown label returns empty response with error in meta."""
        client, session, _app = harness

        with patch("kg.api.routes.graph._LABEL_TO_GROUP", {}):
            resp = await client.get("/api/v1/subgraph", params={"label": "NonExistentLabel"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["nodes"] == []
        assert body["edges"] == []
        assert "error" in body["meta"]
        assert "Unknown or disallowed label" in body["meta"]["error"]

    async def test_subgraph_empty(self, harness: Any) -> None:
        """Known label with no matching data returns empty lists."""
        client, session, _app = harness

        _reset(session, [MockNeo4jResult([])])

        with patch("kg.api.routes.graph._LABEL_TO_GROUP", {"Port": "PhysicalEntity"}):
            resp = await client.get("/api/v1/subgraph", params={"label": "Port", "limit": 10})

        assert resp.status_code == 200
        body = resp.json()
        assert body["nodes"] == []
        assert body["edges"] == []
        assert body["meta"]["nodeCount"] == 0
        assert body["meta"]["edgeCount"] == 0


# ===========================================================================
# TestNeighborsHarness
# ===========================================================================


class TestNeighborsHarness:
    """Tests for GET /api/v1/neighbors."""

    async def test_neighbors_found(self, harness: Any) -> None:
        """Node with 2 neighbors returns center + neighbors + edges."""
        client, session, _app = harness

        center = make_neo4j_node(element_id="4:nb:0", labels=["Vessel", "KG_default"], props={"name": "독도함"})
        nb1 = make_neo4j_node(element_id="4:nb:1", labels=["Port", "KG_default"], props={"name": "부산항"})
        nb2 = make_neo4j_node(element_id="4:nb:2", labels=["Organization", "KG_default"], props={"name": "KRISO"})
        r1 = make_neo4j_relationship(element_id="5:nb:1", rel_type="DOCKED_AT", src_id="4:nb:0", tgt_id="4:nb:1")
        r2 = make_neo4j_relationship(element_id="5:nb:2", rel_type="OPERATED_BY", src_id="4:nb:0", tgt_id="4:nb:2")

        records = [
            _graph_record(center, nb1, r1),
            _graph_record(center, nb2, r2),
        ]
        _reset(session, [MockNeo4jResult(records)])

        resp = await client.get("/api/v1/neighbors", params={"nodeId": "4:nb:0"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["centerNodeId"] == "4:nb:0"
        assert body["meta"]["nodeCount"] == 3  # center + 2 neighbors
        assert body["meta"]["edgeCount"] == 2

    async def test_neighbors_no_results(self, harness: Any) -> None:
        """Non-existent nodeId returns empty neighbors."""
        client, session, _app = harness

        _reset(session, [MockNeo4jResult([])])

        resp = await client.get("/api/v1/neighbors", params={"nodeId": "4:no:999"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["nodes"] == []
        assert body["edges"] == []
        assert body["meta"]["nodeCount"] == 0
        assert body["meta"]["edgeCount"] == 0


# ===========================================================================
# TestSearchHarness
# ===========================================================================


class TestSearchHarness:
    """Tests for GET /api/v1/search."""

    async def test_search_with_results(self, harness: Any) -> None:
        """Search returns matching nodes and edges."""
        client, session, _app = harness

        n1 = make_neo4j_node(element_id="4:s:1", labels=["Port", "KG_default"], props={"name": "부산항"})
        n2 = make_neo4j_node(element_id="4:s:2", labels=["Vessel", "KG_default"], props={"name": "부산호"})
        rel = make_neo4j_relationship(element_id="5:s:1", rel_type="DOCKED_AT", src_id="4:s:2", tgt_id="4:s:1")

        records = [
            _graph_record(n1, n2, rel),
            _graph_record(n2),
        ]
        _reset(session, [MockNeo4jResult(records)])

        resp = await client.get("/api/v1/search", params={"q": "부산", "limit": 30})
        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["query"] == "부산"
        assert body["meta"]["nodeCount"] >= 1

    async def test_search_empty(self, harness: Any) -> None:
        """Search with no matching results returns empty."""
        client, session, _app = harness

        _reset(session, [MockNeo4jResult([])])

        resp = await client.get("/api/v1/search", params={"q": "zzz_no_match_zzz", "limit": 10})
        assert resp.status_code == 200
        body = resp.json()
        assert body["nodes"] == []
        assert body["edges"] == []
        assert body["meta"]["nodeCount"] == 0

    async def test_search_min_query_length(self, harness: Any) -> None:
        """Empty query string fails FastAPI validation (422)."""
        client, session, _app = harness

        resp = await client.get("/api/v1/search", params={"q": ""})
        assert resp.status_code == 422
