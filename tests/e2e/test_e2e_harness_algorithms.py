"""E2E harness tests for algorithm endpoints (/api/v1/algorithms/*).

Tests GDS algorithm execution, status checks, and error handling using
MockNeo4jSession -- no real Neo4j needed.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from tests.helpers.mock_neo4j import (
    MockNeo4jResult,
    make_neo4j_node,
)
from tests.e2e.conftest import _reset

pytestmark = [
    pytest.mark.unit,
    pytest.mark.asyncio,
]


# ===========================================================================
# Algorithm List
# ===========================================================================


class TestAlgorithmList:
    """GET /api/v1/algorithms endpoint tests."""

    async def test_list_algorithms(self, harness: Any) -> None:
        """List returns all supported GDS algorithm names."""
        client, _session, _app = harness

        resp = await client.get("/api/v1/algorithms")
        assert resp.status_code == 200
        body = resp.json()
        assert "algorithms" in body
        algos = body["algorithms"]
        assert isinstance(algos, list)
        assert len(algos) >= 5
        # Known algorithms
        assert "pageRank" in algos
        assert "louvain" in algos
        assert "dijkstra" in algos
        assert "nodeSimilarity" in algos


# ===========================================================================
# Algorithm Execution
# ===========================================================================


class TestAlgorithmExecution:
    """POST /api/v1/algorithms/* endpoint tests."""

    async def test_pagerank(self, harness: Any) -> None:
        """PageRank returns results with algorithm metadata."""
        client, session, _app = harness

        node = make_neo4j_node(
            element_id="4:alg:1",
            labels=["Vessel"],
            props={"name": "TestVessel"},
        )
        _reset(
            session,
            [MockNeo4jResult([{"node": node, "score": 0.42}])],
        )

        resp = await client.post(
            "/api/v1/algorithms/pagerank",
            json={
                "label": "Vessel",
                "relationshipType": "DOCKED_AT",
                "iterations": 10,
                "dampingFactor": 0.85,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["algorithm"] == "pagerank"
        assert "cypher" in body
        assert len(body["results"]) == 1
        assert body["meta"]["label"] == "Vessel"
        assert body["meta"]["iterations"] == 10

    async def test_community(self, harness: Any) -> None:
        """Community detection (Louvain) returns valid response."""
        client, session, _app = harness

        _reset(
            session,
            [MockNeo4jResult([{"nodeId": 1, "communityId": 0}])],
        )

        resp = await client.post(
            "/api/v1/algorithms/community",
            json={
                "label": "Port",
                "relationshipType": "ROUTE_TO",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["algorithm"] == "louvain"
        assert body["meta"]["label"] == "Port"

    async def test_centrality(self, harness: Any) -> None:
        """Betweenness centrality returns valid response."""
        client, session, _app = harness

        _reset(
            session,
            [MockNeo4jResult([{"nodeId": 1, "score": 0.75}])],
        )

        resp = await client.post(
            "/api/v1/algorithms/centrality",
            json={
                "label": "Organization",
                "relationshipType": "OPERATES",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["algorithm"] == "betweenness"

    async def test_shortest_path(self, harness: Any) -> None:
        """Shortest path (Dijkstra) returns valid response."""
        client, session, _app = harness

        _reset(
            session,
            [MockNeo4jResult([{"totalCost": 42.5, "path": [1, 2, 3]}])],
        )

        resp = await client.post(
            "/api/v1/algorithms/shortest-path",
            json={
                "sourceId": "V-001",
                "targetId": "PORT-BUS",
                "relationshipType": "ROUTE_TO",
                "weightProperty": "distance",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["algorithm"] == "dijkstra"
        assert body["meta"]["sourceId"] == "V-001"
        assert body["meta"]["targetId"] == "PORT-BUS"

    async def test_similarity(self, harness: Any) -> None:
        """Node similarity returns valid response."""
        client, session, _app = harness

        _reset(
            session,
            [MockNeo4jResult([{"node1": 1, "node2": 2, "similarity": 0.88}])],
        )

        resp = await client.post(
            "/api/v1/algorithms/similarity",
            json={
                "label": "Vessel",
                "relationshipType": "DOCKED_AT",
                "topK": 5,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["algorithm"] == "nodeSimilarity"
        assert body["meta"]["topK"] == 5

    async def test_algorithm_empty_results(self, harness: Any) -> None:
        """Algorithm returning no records yields an empty results list."""
        client, session, _app = harness

        _reset(session, [MockNeo4jResult([])])

        resp = await client.post(
            "/api/v1/algorithms/pagerank",
            json={
                "label": "EmptyLabel",
                "relationshipType": "NONE",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["results"] == []

    async def test_algorithm_execution_error(self, harness: Any) -> None:
        """Session error during algorithm execution returns 500."""
        client, session, _app = harness

        session.run = AsyncMock(side_effect=Exception("internal failure"))

        resp = await client.post(
            "/api/v1/algorithms/pagerank",
            json={
                "label": "Vessel",
                "relationshipType": "DOCKED_AT",
            },
        )
        assert resp.status_code == 500
        assert "execution failed" in resp.json()["detail"]


# ===========================================================================
# GDS Status
# ===========================================================================


class TestGDSStatus:
    """GET /api/v1/algorithms/gds-status endpoint tests."""

    async def test_gds_status_available(self, harness: Any) -> None:
        """GDS available: returns version string."""
        client, session, _app = harness

        _reset(session, [MockNeo4jResult([{"version": "2.6.0"}])])

        resp = await client.get("/api/v1/algorithms/gds-status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["available"] is True
        assert body["version"] == "2.6.0"

    async def test_gds_status_unavailable(self, harness: Any) -> None:
        """Session error (GDS not installed) returns available=false."""
        client, session, _app = harness

        session.run = AsyncMock(side_effect=Exception("procedure not found"))

        resp = await client.get("/api/v1/algorithms/gds-status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["available"] is False
        assert body["version"] is None
