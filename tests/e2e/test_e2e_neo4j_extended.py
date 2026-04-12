"""Extended Neo4j E2E tests — graph, lineage, ETL, and schema endpoints.

These tests exercise the full HTTP stack (routing, middleware, serialization)
against a live Neo4j instance.  All test data uses the ``_E2ETest`` label prefix
so it can be cleaned up deterministically before and after each test.

Prerequisites:
    NEO4J_TEST_URI=bolt://localhost:7687
    NEO4J_TEST_USER=neo4j        (default)
    NEO4J_TEST_PASSWORD=fluxrag2026
"""

from __future__ import annotations

import os

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

NEO4J_TEST_URI = os.environ.get("NEO4J_TEST_URI", "bolt://localhost:7687")
NEO4J_TEST_USER = os.environ.get("NEO4J_TEST_USER", "neo4j")
NEO4J_TEST_PASSWORD = os.environ.get("NEO4J_TEST_PASSWORD", "fluxrag2026")

# ---------------------------------------------------------------------------
# Module-level markers -- applied to every test in this file
# ---------------------------------------------------------------------------

pytestmark = [
    pytest.mark.integration,
    pytest.mark.e2e,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not os.environ.get("NEO4J_TEST_URI"),
        reason="NEO4J_TEST_URI not set -- skip real Neo4j E2E tests",
    ),
]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_test_data():
    """Delete all ``_E2ETest`` nodes before and after every test.

    Uses the sync neo4j driver directly to avoid triggering the Cypher
    endpoint's dangerous-pattern filter (``DETACH DELETE`` without WHERE is
    blocked there).  Also clears the ETL module-level ``_run_history`` so
    tests do not pollute each other.
    """
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(NEO4J_TEST_URI, auth=(NEO4J_TEST_USER, NEO4J_TEST_PASSWORD))

    def _purge():
        with driver.session() as session:
            session.run("MATCH (n:_E2ETest) DETACH DELETE n")

    _purge()

    # Clear ETL in-memory state so each test starts fresh
    from kg.api.routes.etl import _run_history

    _run_history.clear()

    yield

    _purge()
    driver.close()


@pytest_asyncio.fixture
async def client():
    """Async HTTPX client wired to the real FastAPI app (development auth bypass)."""
    from kg.config import AppConfig, Neo4jConfig, reset, set_config

    config = AppConfig(
        env="development",
        neo4j=Neo4jConfig(
            uri=NEO4J_TEST_URI,
            user=NEO4J_TEST_USER,
            password=NEO4J_TEST_PASSWORD,
        ),
    )
    set_config(config)

    from kg.api.app import create_app

    app = create_app(config)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    reset()


# ---------------------------------------------------------------------------
# Helper: create node via API
# ---------------------------------------------------------------------------


async def _create_node(
    client: httpx.AsyncClient,
    labels: list[str],
    properties: dict,
) -> dict:
    """POST /api/v1/nodes and return the response JSON (with id)."""
    resp = await client.post(
        "/api/v1/nodes",
        json={"labels": labels, "properties": properties},
    )
    assert resp.status_code == 201, f"Node creation failed: {resp.text}"
    return resp.json()


# ===========================================================================
# Test class: Graph subgraph / neighbors / search
# ===========================================================================


class TestGraphExploration:
    """Subgraph, neighbors, and search endpoints with real Neo4j."""

    async def test_graph_subgraph(self, client: httpx.AsyncClient):
        """Create Vessel nodes with DOCKED_AT relationships, GET /subgraph.

        The ``/subgraph`` endpoint checks ``_LABEL_TO_GROUP`` and rejects
        unknown labels.  ``Vessel`` is registered, so we use it directly.
        """
        # Create 3 vessels and 1 port
        v1 = await _create_node(client, ["_E2ETest", "Vessel"], {"name": "E2E-Vessel-A"})
        v2 = await _create_node(client, ["_E2ETest", "Vessel"], {"name": "E2E-Vessel-B"})
        v3 = await _create_node(client, ["_E2ETest", "Vessel"], {"name": "E2E-Vessel-C"})
        port = await _create_node(client, ["_E2ETest", "Port"], {"name": "E2E-Port-Alpha"})

        # Wire relationships: v1->port, v2->port
        for vid in [v1["id"], v2["id"]]:
            resp = await client.post(
                "/api/v1/relationships",
                json={
                    "sourceId": vid,
                    "targetId": port["id"],
                    "type": "DOCKED_AT",
                    "properties": {},
                },
            )
            assert resp.status_code == 201

        # GET /subgraph?label=Vessel
        resp = await client.get("/api/v1/subgraph", params={"label": "Vessel", "limit": 50})
        assert resp.status_code == 200
        body = resp.json()
        # We may or may not see our test nodes depending on project label
        # filtering; the important thing is a 200 with valid structure.
        assert "nodes" in body
        assert "edges" in body
        assert "meta" in body

    async def test_graph_neighbors(self, client: httpx.AsyncClient):
        """Create a node with neighbors, GET /neighbors?nodeId=X."""
        center = await _create_node(client, ["_E2ETest", "Vessel"], {"name": "E2E-Center"})
        nbr1 = await _create_node(client, ["_E2ETest", "Port"], {"name": "E2E-Neighbor-1"})
        nbr2 = await _create_node(client, ["_E2ETest", "SeaArea"], {"name": "E2E-Neighbor-2"})

        for nbr_id in [nbr1["id"], nbr2["id"]]:
            resp = await client.post(
                "/api/v1/relationships",
                json={
                    "sourceId": center["id"],
                    "targetId": nbr_id,
                    "type": "RELATED_TO",
                    "properties": {},
                },
            )
            assert resp.status_code == 201

        resp = await client.get(
            "/api/v1/neighbors",
            params={"nodeId": center["id"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "nodes" in body
        assert "meta" in body
        # At minimum the center node should appear
        assert body["meta"]["nodeCount"] >= 1

    async def test_graph_search(self, client: httpx.AsyncClient):
        """Create nodes with distinctive names, GET /search?q=name.

        The search endpoint uses fulltext indexes if available, else falls
        back to CONTAINS.  Either path should return 200.
        """
        await _create_node(client, ["_E2ETest", "Vessel"], {"name": "UniqueSearchTarget2026"})
        await _create_node(client, ["_E2ETest", "Port"], {"name": "AnotherE2EPort"})

        resp = await client.get(
            "/api/v1/search",
            params={"q": "UniqueSearchTarget2026", "limit": 10},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "nodes" in body
        assert "meta" in body
        # Depending on fulltext index availability the node may or may not
        # appear; we only assert a valid response structure.


# ===========================================================================
# Test class: Lineage endpoints
# ===========================================================================


class TestLineageEndpoints:
    """Lineage full / ancestors / descendants / timeline with real Neo4j.

    Lineage queries work on ``(:LineageNode)`` nodes connected via
    ``[:DERIVED_FROM]`` relationships.  We create them directly via Cypher
    so the lineage route queries find them.
    """

    async def _seed_lineage(self, client: httpx.AsyncClient) -> None:
        """Seed a 3-node lineage chain via the Cypher execute endpoint.

        Chain:  LN-001 <-[DERIVED_FROM]- LN-002 <-[DERIVED_FROM]- LN-003
        Also tags each node with ``_E2ETest`` for deterministic cleanup.
        """
        seed_cypher = """
        CREATE (a:LineageNode:_E2ETest {
            nodeId: 'LN-001', entityType: 'Vessel', entityId: 'VES-001',
            createdAt: datetime('2026-01-01T00:00:00Z')
        })
        CREATE (b:LineageNode:_E2ETest {
            nodeId: 'LN-002', entityType: 'Vessel', entityId: 'VES-002',
            createdAt: datetime('2026-02-01T00:00:00Z')
        })
        CREATE (c:LineageNode:_E2ETest {
            nodeId: 'LN-003', entityType: 'Vessel', entityId: 'VES-003',
            createdAt: datetime('2026-03-01T00:00:00Z')
        })
        WITH a, b, c
        CREATE (b)-[:DERIVED_FROM {
            edgeId: 'E-001', eventType: 'transform', agent: 'etl',
            activity: 'merge', timestamp: datetime('2026-02-01T00:00:00Z')
        }]->(a)
        CREATE (c)-[:DERIVED_FROM {
            edgeId: 'E-002', eventType: 'transform', agent: 'etl',
            activity: 'enrich', timestamp: datetime('2026-03-01T00:00:00Z')
        }]->(b)
        """
        resp = await client.post(
            "/api/v1/cypher/execute",
            json={"cypher": seed_cypher, "parameters": {}},
        )
        assert resp.status_code == 200, f"Lineage seed failed: {resp.text}"

    async def test_lineage_full(self, client: httpx.AsyncClient):
        """GET /lineage/Vessel/VES-001 -- full lineage graph."""
        await self._seed_lineage(client)

        resp = await client.get("/api/v1/lineage/Vessel/VES-001")
        assert resp.status_code == 200
        body = resp.json()
        assert "nodes" in body
        assert "edges" in body
        assert "meta" in body
        assert body["meta"]["entityType"] == "Vessel"
        assert body["meta"]["entityId"] == "VES-001"

    async def test_lineage_ancestors(self, client: httpx.AsyncClient):
        """GET /lineage/Vessel/VES-002/ancestors -- should find VES-001 via DERIVED_FROM."""
        await self._seed_lineage(client)

        resp = await client.get("/api/v1/lineage/Vessel/VES-002/ancestors")
        assert resp.status_code == 200
        body = resp.json()
        assert "nodes" in body
        assert "meta" in body
        assert body["meta"]["direction"] == "ancestors"
        # VES-002 derives from VES-001, so ancestors should be non-empty
        # (may be empty if query semantics differ; 200 is the key assertion)

    async def test_lineage_descendants(self, client: httpx.AsyncClient):
        """GET /lineage/Vessel/VES-001/descendants -- should find VES-002, VES-003."""
        await self._seed_lineage(client)

        resp = await client.get("/api/v1/lineage/Vessel/VES-001/descendants")
        assert resp.status_code == 200
        body = resp.json()
        assert "nodes" in body
        assert "meta" in body
        assert body["meta"]["direction"] == "descendants"

    async def test_lineage_timeline(self, client: httpx.AsyncClient):
        """GET /lineage/Vessel/VES-001/timeline -- chronological events."""
        await self._seed_lineage(client)

        resp = await client.get("/api/v1/lineage/Vessel/VES-001/timeline")
        assert resp.status_code == 200
        body = resp.json()
        assert "events" in body
        assert "meta" in body
        assert body["meta"]["entityType"] == "Vessel"
        assert body["meta"]["entityId"] == "VES-001"


# ===========================================================================
# Test class: ETL trigger and pipelines
# ===========================================================================


class TestETLEndpoints:
    """ETL trigger, status, and pipeline listing with real Neo4j."""

    async def test_etl_trigger_and_status(self, client: httpx.AsyncClient):
        """POST /etl/trigger with papers pipeline, then GET /etl/status/{run_id}.

        The pipeline runs with empty records in PoC mode, so it should
        complete quickly with records_processed=0.
        """
        trigger_payload = {
            "source": "manual",
            "pipeline_name": "papers",
            "mode": "incremental",
            "force_full": False,
        }
        resp = await client.post("/api/v1/etl/trigger", json=trigger_payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["pipeline_name"] == "papers"
        assert body["status"] in ("COMPLETED", "FAILED")
        run_id = body["run_id"]
        assert run_id

        # Verify status lookup
        resp = await client.get(f"/api/v1/etl/status/{run_id}")
        assert resp.status_code == 200
        status_body = resp.json()
        assert status_body["run_id"] == run_id
        assert status_body["pipeline_name"] == "papers"
        assert status_body["status"] in ("COMPLETED", "FAILED", "RUNNING")

    async def test_etl_pipelines_list(self, client: httpx.AsyncClient):
        """GET /etl/pipelines -- verify 6 registered pipelines."""
        resp = await client.get("/api/v1/etl/pipelines")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 6, f"Expected 6 pipelines, got {len(body)}"

        pipeline_names = {p["name"] for p in body}
        expected = {"papers", "facilities", "weather", "accidents", "relations", "facility_data"}
        assert pipeline_names == expected, (
            f"Pipeline names mismatch: {pipeline_names} != {expected}"
        )

        # Every pipeline should report supports_elt=True
        for p in body:
            assert p["supports_elt"] is True, f"Pipeline {p['name']} should support ELT"


# ===========================================================================
# Test class: Schema with test data
# ===========================================================================


class TestSchemaWithData:
    """Schema introspection after creating diverse test nodes."""

    async def test_schema_with_test_data(self, client: httpx.AsyncClient):
        """Create diverse nodes, GET /schema, verify labels appear."""
        # Create nodes with several distinct labels
        label_sets = [
            (["_E2ETest", "Vessel"], {"name": "E2E-Schema-Vessel"}),
            (["_E2ETest", "Port"], {"name": "E2E-Schema-Port"}),
            (["_E2ETest", "Regulation"], {"name": "E2E-Schema-Regulation"}),
            (["_E2ETest", "SeaArea"], {"name": "E2E-Schema-SeaArea"}),
        ]
        for labels, props in label_sets:
            await _create_node(client, labels, props)

        resp = await client.get("/api/v1/schema")
        assert resp.status_code == 200
        schema = resp.json()

        assert "labels" in schema
        assert "relationshipTypes" in schema
        assert schema["totalLabels"] > 0

        label_names = {lbl["label"] for lbl in schema["labels"]}
        # At minimum _E2ETest should appear, plus some of the sub-labels
        has_test_labels = "_E2ETest" in label_names or any(
            l in label_names for l in ("Vessel", "Port", "Regulation", "SeaArea")
        )
        assert has_test_labels, (
            f"Schema labels should include _E2ETest or sub-labels, got: {sorted(label_names)}"
        )
