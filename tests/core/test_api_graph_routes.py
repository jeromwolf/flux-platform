"""Unit tests for core/kg/api/routes/graph.py.

Tests helper functions and HTTP endpoints without a live Neo4j instance.
All tests are ``@pytest.mark.unit``.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from kg.config import AppConfig, Neo4jConfig, reset

from tests.helpers.mock_neo4j import (
    FakeNode,
    FakeRelationship,
    MockNeo4jResult,
    MockNeo4jSession,
    make_neo4j_node,
    make_neo4j_relationship,
    make_test_app,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_config():
    reset()
    yield
    reset()


@pytest.fixture
def dev_config() -> AppConfig:
    return AppConfig(env="development", neo4j=Neo4jConfig(uri="bolt://mock:7687"))


def _make_graph_record(
    node_n: Any = None,
    node_m: Any = None,
    rel_r: Any = None,
) -> dict[str, Any]:
    """Assemble a record dict with keys n, r, m."""
    return {"n": node_n, "r": rel_r, "m": node_m}


# ---------------------------------------------------------------------------
# _extract_node
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExtractNode:
    """Tests for the _extract_node() helper."""

    def test_returns_none_for_missing_key(self):
        """Record without the key returns None."""
        from kg.api.routes.graph import _extract_node

        record = {}
        assert _extract_node(record, "n") is None

    def test_returns_none_for_non_node_value(self):
        """Plain dict without element_id/labels returns None."""
        from kg.api.routes.graph import _extract_node

        record = {"n": {"just": "a dict"}}
        result = _extract_node(record, "n")
        assert result is None

    def test_extracts_node_fields(self):
        """FakeNode with element_id and labels should be extracted correctly."""
        from kg.api.routes.graph import _extract_node

        node = make_neo4j_node(element_id="4:a:1", labels=["Vessel"], props={"name": "Sea Eagle"})
        record = {"n": node}
        result = _extract_node(record, "n")

        assert result is not None
        assert result["id"] == "4:a:1"
        assert "Vessel" in result["labels"]
        assert result["primaryLabel"] == "Vessel"
        assert result["properties"]["name"] == "Sea Eagle"
        assert result["displayName"] == "Sea Eagle"

    def test_display_name_falls_back_to_title(self):
        """displayName should use 'title' when 'name' is absent."""
        from kg.api.routes.graph import _extract_node

        node = make_neo4j_node(props={"title": "My Title"})
        record = {"n": node}
        result = _extract_node(record, "n")

        assert result is not None
        assert result["displayName"] == "My Title"

    def test_display_name_falls_back_to_primary_label(self):
        """When neither 'name' nor 'title' exists, use primaryLabel."""
        from kg.api.routes.graph import _extract_node

        node = make_neo4j_node(labels=["Port"], props={"code": "KRPUS"})
        record = {"n": node}
        result = _extract_node(record, "n")

        assert result is not None
        assert result["displayName"] == "Port"

    def test_returns_none_when_value_is_none(self):
        """Record with key explicitly set to None returns None."""
        from kg.api.routes.graph import _extract_node

        record = {"n": None}
        assert _extract_node(record, "n") is None

    def test_handles_key_error_gracefully(self):
        """Record that raises KeyError on access returns None."""
        from kg.api.routes.graph import _extract_node

        class BadRecord:
            def __getitem__(self, k):
                raise KeyError(k)

        result = _extract_node(BadRecord(), "n")
        assert result is None


# ---------------------------------------------------------------------------
# _extract_relationship
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExtractRelationship:
    """Tests for the _extract_relationship() helper."""

    def test_returns_none_for_missing_key(self):
        """Record without the key returns None."""
        from kg.api.routes.graph import _extract_relationship

        record = {}
        assert _extract_relationship(record, "r") is None

    def test_returns_none_for_plain_dict(self):
        """Plain dict without type/start_node returns None."""
        from kg.api.routes.graph import _extract_relationship

        record = {"r": {"just": "a dict"}}
        assert _extract_relationship(record, "r") is None

    def test_extracts_relationship_fields(self):
        """FakeRelationship should be extracted with all expected fields."""
        from kg.api.routes.graph import _extract_relationship

        rel = make_neo4j_relationship(
            element_id="5:a:1",
            rel_type="DOCKED_AT",
            src_id="4:a:1",
            tgt_id="4:a:2",
            props={"since": "2026"},
        )
        record = {"r": rel}
        result = _extract_relationship(record, "r")

        assert result is not None
        assert result["id"] == "5:a:1"
        assert result["type"] == "DOCKED_AT"
        assert result["sourceId"] == "4:a:1"
        assert result["targetId"] == "4:a:2"
        assert result["properties"]["since"] == "2026"

    def test_returns_none_when_value_is_none(self):
        """Record with key explicitly set to None returns None."""
        from kg.api.routes.graph import _extract_relationship

        record = {"r": None}
        assert _extract_relationship(record, "r") is None


# ---------------------------------------------------------------------------
# _collect_graph
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCollectGraph:
    """Tests for the _collect_graph() helper."""

    def test_empty_records_returns_empty_dicts(self):
        """Empty list → empty nodes and edges."""
        from kg.api.routes.graph import _collect_graph

        nodes, edges = _collect_graph([])
        assert nodes == {}
        assert edges == {}

    def test_single_node_record(self):
        """Single record with only 'n' → one node, no edges."""
        from kg.api.routes.graph import _collect_graph

        node = make_neo4j_node(element_id="4:a:1")
        records = [{"n": node, "r": None, "m": None}]
        nodes, edges = _collect_graph(records)

        assert len(nodes) == 1
        assert "4:a:1" in nodes
        assert edges == {}

    def test_deduplicates_nodes(self):
        """Same node appearing in multiple records is stored only once."""
        from kg.api.routes.graph import _collect_graph

        node = make_neo4j_node(element_id="4:a:1")
        records = [
            {"n": node, "r": None, "m": None},
            {"n": node, "r": None, "m": None},
        ]
        nodes, edges = _collect_graph(records)
        assert len(nodes) == 1

    def test_collects_both_n_and_m_nodes(self):
        """Records with both 'n' and 'm' nodes yield two unique nodes."""
        from kg.api.routes.graph import _collect_graph

        node_n = make_neo4j_node(element_id="4:a:1")
        node_m = make_neo4j_node(element_id="4:a:2", labels=["Port"], props={"name": "Busan"})
        rel = make_neo4j_relationship(src_id="4:a:1", tgt_id="4:a:2")
        records = [{"n": node_n, "r": rel, "m": node_m}]

        nodes, edges = _collect_graph(records)
        assert len(nodes) == 2
        assert "4:a:1" in nodes
        assert "4:a:2" in nodes
        assert len(edges) == 1

    def test_deduplicates_edges(self):
        """Same relationship in multiple records is stored only once."""
        from kg.api.routes.graph import _collect_graph

        node_n = make_neo4j_node(element_id="4:a:1")
        node_m = make_neo4j_node(element_id="4:a:2", labels=["Port"], props={})
        rel = make_neo4j_relationship(element_id="5:a:1", src_id="4:a:1", tgt_id="4:a:2")
        records = [
            {"n": node_n, "r": rel, "m": node_m},
            {"n": node_n, "r": rel, "m": node_m},
        ]
        _, edges = _collect_graph(records)
        assert len(edges) == 1


# ---------------------------------------------------------------------------
# /graph/neighbors endpoint
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNeighborsEndpoint:
    """Tests for GET /graph/neighbors."""

    def test_neighbors_returns_graph_response(self, dev_config: AppConfig):
        """Valid nodeId query returns a GraphResponse JSON structure."""
        node_n = make_neo4j_node(element_id="4:a:99", labels=["Vessel"], props={"name": "Alpha"})
        node_m = make_neo4j_node(element_id="4:a:100", labels=["Port"], props={"name": "Beta"})
        rel = make_neo4j_relationship(src_id="4:a:99", tgt_id="4:a:100")
        record = {"n": node_n, "r": rel, "m": node_m}

        session = MockNeo4jSession(side_effects=[MockNeo4jResult([record])])
        client = make_test_app(session, dev_config)

        resp = client.get("/api/v1/neighbors?nodeId=4:a:99")
        assert resp.status_code == 200
        body = resp.json()
        assert "nodes" in body
        assert "edges" in body
        assert "meta" in body
        assert body["meta"]["centerNodeId"] == "4:a:99"

    def test_neighbors_empty_result(self, dev_config: AppConfig):
        """nodeId that matches no records returns empty nodes/edges."""
        session = MockNeo4jSession(side_effects=[MockNeo4jResult([])])
        client = make_test_app(session, dev_config)

        resp = client.get("/api/v1/neighbors?nodeId=nonexistent-id")
        assert resp.status_code == 200
        body = resp.json()
        assert body["nodes"] == []
        assert body["edges"] == []

    def test_neighbors_missing_node_id_returns_422(self, dev_config: AppConfig):
        """Missing nodeId query parameter returns HTTP 422."""
        session = MockNeo4jSession()
        client = make_test_app(session, dev_config)

        resp = client.get("/api/v1/neighbors")
        assert resp.status_code == 422

    def test_neighbors_meta_contains_counts(self, dev_config: AppConfig):
        """meta should include nodeCount and edgeCount."""
        node = make_neo4j_node(element_id="4:a:1")
        record = {"n": node, "r": None, "m": None}
        session = MockNeo4jSession(side_effects=[MockNeo4jResult([record])])
        client = make_test_app(session, dev_config)

        resp = client.get("/api/v1/neighbors?nodeId=4:a:1")
        body = resp.json()
        assert "nodeCount" in body["meta"]
        assert "edgeCount" in body["meta"]


# ---------------------------------------------------------------------------
# /graph/subgraph endpoint
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSubgraphEndpoint:
    """Tests for GET /graph/subgraph."""

    def _mock_label_to_group(self, label: str = "Vessel") -> dict[str, str]:
        return {label: "PhysicalEntity"}

    def test_subgraph_unknown_label_returns_error_meta(self, dev_config: AppConfig):
        """Unknown label not in _LABEL_TO_GROUP returns error in meta."""
        session = MockNeo4jSession()
        client = make_test_app(session, dev_config)

        # Patch _LABEL_TO_GROUP to be empty so all labels are "unknown"
        with patch("kg.api.routes.graph._LABEL_TO_GROUP", {}):
            resp = client.get("/api/v1/subgraph?label=NonExistent")

        assert resp.status_code == 200
        body = resp.json()
        assert "error" in body["meta"]
        assert body["nodes"] == []

    def test_subgraph_known_label_queries_session(self, dev_config: AppConfig):
        """Known label triggers session.run() and returns graph data."""
        node = make_neo4j_node(element_id="4:a:5", labels=["Vessel"], props={"name": "Sea Wolf"})
        record = {"n": node, "r": None, "m": None}
        session = MockNeo4jSession(side_effects=[MockNeo4jResult([record])])
        client = make_test_app(session, dev_config)

        with patch("kg.api.routes.graph._LABEL_TO_GROUP", {"Vessel": "PhysicalEntity"}):
            resp = client.get("/api/v1/subgraph?label=Vessel&limit=10")

        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["label"] == "Vessel"
        assert body["meta"]["limit"] == 10
        assert len(body["nodes"]) >= 1

    def test_subgraph_default_label_is_vessel(self, dev_config: AppConfig):
        """When no label query param is given, default is 'Vessel'."""
        session = MockNeo4jSession(side_effects=[MockNeo4jResult([])])
        client = make_test_app(session, dev_config)

        with patch("kg.api.routes.graph._LABEL_TO_GROUP", {"Vessel": "PhysicalEntity"}):
            resp = client.get("/api/v1/subgraph")

        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["label"] == "Vessel"

    def test_subgraph_limit_above_max_returns_422(self, dev_config: AppConfig):
        """Limit > 200 should fail FastAPI validation (422)."""
        session = MockNeo4jSession()
        client = make_test_app(session, dev_config)

        resp = client.get("/api/v1/subgraph?label=Vessel&limit=999")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /graph/search endpoint
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSearchEndpoint:
    """Tests for GET /graph/search."""

    def test_search_returns_graph_response(self, dev_config: AppConfig):
        """Valid query returns a GraphResponse with nodes/edges/meta."""
        node = make_neo4j_node(element_id="4:a:10", labels=["Vessel"], props={"name": "Fast Ship"})
        record = {"n": node, "r": None, "m": None}
        session = MockNeo4jSession(side_effects=[MockNeo4jResult([record])])
        client = make_test_app(session, dev_config)

        resp = client.get("/api/v1/search?q=ship")
        assert resp.status_code == 200
        body = resp.json()
        assert "nodes" in body
        assert "edges" in body
        assert body["meta"]["query"] == "ship"

    def test_search_missing_q_returns_422(self, dev_config: AppConfig):
        """Missing required 'q' parameter returns HTTP 422."""
        session = MockNeo4jSession()
        client = make_test_app(session, dev_config)

        resp = client.get("/api/v1/search")
        assert resp.status_code == 422

    def test_search_empty_q_returns_422(self, dev_config: AppConfig):
        """Empty string 'q' (min_length=1) returns HTTP 422."""
        session = MockNeo4jSession()
        client = make_test_app(session, dev_config)

        resp = client.get("/api/v1/search?q=")
        assert resp.status_code == 422

    def test_search_limit_above_max_returns_422(self, dev_config: AppConfig):
        """Limit > 100 should fail FastAPI validation (422)."""
        session = MockNeo4jSession()
        client = make_test_app(session, dev_config)

        resp = client.get("/api/v1/search?q=vessel&limit=999")
        assert resp.status_code == 422

    def test_search_meta_contains_query(self, dev_config: AppConfig):
        """Response meta should echo back the query string."""
        session = MockNeo4jSession(side_effects=[MockNeo4jResult([])])
        client = make_test_app(session, dev_config)

        resp = client.get("/api/v1/search?q=tanker")
        body = resp.json()
        assert body["meta"]["query"] == "tanker"

    def test_search_fallback_when_no_fulltext_indexes(self, dev_config: AppConfig):
        """When FULLTEXT_INDEX_MAP is empty, fallback CONTAINS cypher is used."""
        node = make_neo4j_node(element_id="4:a:20", labels=["Vessel"], props={"name": "Echo"})
        record = {"n": node, "r": None, "m": None}
        session = MockNeo4jSession(side_effects=[MockNeo4jResult([record])])
        client = make_test_app(session, dev_config)

        # Patch the dict at the source module so the local import inside the
        # function body picks up the empty mapping.
        with patch("kg.fulltext.FULLTEXT_INDEX_MAP", {}):
            resp = client.get("/api/v1/search?q=echo")

        assert resp.status_code == 200
        body = resp.json()
        assert "nodes" in body
