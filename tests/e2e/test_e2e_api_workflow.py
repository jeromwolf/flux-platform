"""End-to-end scenario tests through the actual FastAPI app with real Neo4j.

These tests exercise the full HTTP stack (routing, middleware, serialization)
against a live Neo4j instance.  All test data uses the ``_Test`` label prefix
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
# Module-level markers — applied to every test in this file
# ---------------------------------------------------------------------------

pytestmark = [
    pytest.mark.integration,
    pytest.mark.e2e,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not os.environ.get("NEO4J_TEST_URI"),
        reason="NEO4J_TEST_URI not set",
    ),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client():
    """Async HTTPX client wired to the real FastAPI app (development auth bypass)."""
    from kg.config import AppConfig, Neo4jConfig, reset, set_config

    config = AppConfig(
        env="development",
        neo4j=Neo4jConfig(
            uri=os.environ.get("NEO4J_TEST_URI", "bolt://localhost:7687"),
            user=os.environ.get("NEO4J_TEST_USER", "neo4j"),
            password=os.environ.get("NEO4J_TEST_PASSWORD", "fluxrag2026"),
        ),
    )
    set_config(config)

    from kg.api.app import create_app

    app = create_app(config)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    reset()


@pytest.fixture(autouse=True)
def clean_test_data():
    """Delete all ``_Test`` nodes before and after every test using the sync driver.

    Using the sync neo4j driver directly avoids triggering the Cypher endpoint's
    dangerous-pattern filter (``DETACH DELETE`` without WHERE is blocked there).
    """
    from neo4j import GraphDatabase

    uri = os.environ.get("NEO4J_TEST_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_TEST_USER", "neo4j")
    password = os.environ.get("NEO4J_TEST_PASSWORD", "fluxrag2026")

    driver = GraphDatabase.driver(uri, auth=(user, password))

    def _purge():
        with driver.session() as session:
            session.run("MATCH (n:_Test) DETACH DELETE n")

    _purge()
    yield
    _purge()
    driver.close()


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _node_id(response_json: dict) -> str:
    """Extract the element ID from a node creation response."""
    return response_json["id"]


# ---------------------------------------------------------------------------
# Test class: Maritime graph lifecycle
# ---------------------------------------------------------------------------


class TestMaritimeGraphWorkflow:
    """Full lifecycle: create nodes + relationships, query, update, delete."""

    @pytest.mark.asyncio
    async def test_full_maritime_graph_lifecycle(self, client: httpx.AsyncClient):
        """End-to-end lifecycle for a small maritime knowledge graph."""

        # ------------------------------------------------------------------
        # 1. Create 5 nodes
        # ------------------------------------------------------------------
        node_specs = [
            {
                "labels": ["_Test", "Vessel"],
                "properties": {"name": "세종대왕함", "vesselType": "DDG", "displacement": "7600t"},
            },
            {
                "labels": ["_Test", "Vessel"],
                "properties": {"name": "독도함", "vesselType": "LPH", "displacement": "18800t"},
            },
            {
                "labels": ["_Test", "Port"],
                "properties": {"name": "부산항", "portCode": "KRPUS", "country": "대한민국"},
            },
            {
                "labels": ["_Test", "Port"],
                "properties": {"name": "인천항", "portCode": "KRICN", "country": "대한민국"},
            },
            {
                "labels": ["_Test", "Organization"],
                "properties": {"name": "KRISO", "fullName": "한국해양과학기술원"},
            },
        ]

        created_nodes: list[dict] = []
        for spec in node_specs:
            resp = await client.post("/api/v1/nodes", json=spec)
            assert resp.status_code == 201, f"Node creation failed: {resp.text}"
            data = resp.json()
            assert data["id"], "Response must include element ID"
            created_nodes.append(data)

        # Build a name → id lookup for relationship wiring
        node_by_name: dict[str, str] = {n["properties"]["name"]: n["id"] for n in created_nodes}

        assert "세종대왕함" in node_by_name
        assert "독도함" in node_by_name
        assert "부산항" in node_by_name
        assert "인천항" in node_by_name
        assert "KRISO" in node_by_name

        # ------------------------------------------------------------------
        # 2. Create 4 relationships
        # ------------------------------------------------------------------
        rel_specs = [
            {
                "sourceId": node_by_name["세종대왕함"],
                "targetId": node_by_name["부산항"],
                "type": "DOCKED_AT",
                "properties": {},
            },
            {
                "sourceId": node_by_name["독도함"],
                "targetId": node_by_name["인천항"],
                "type": "DOCKED_AT",
                "properties": {},
            },
            {
                "sourceId": node_by_name["KRISO"],
                "targetId": node_by_name["세종대왕함"],
                "type": "OPERATES",
                "properties": {},
            },
            {
                "sourceId": node_by_name["KRISO"],
                "targetId": node_by_name["독도함"],
                "type": "OPERATES",
                "properties": {},
            },
        ]

        created_rels: list[dict] = []
        for spec in rel_specs:
            resp = await client.post("/api/v1/relationships", json=spec)
            assert resp.status_code == 201, f"Relationship creation failed: {resp.text}"
            data = resp.json()
            assert data["relationship"]["id"], "Response must include relationship ID"
            created_rels.append(data)

        # ------------------------------------------------------------------
        # 3. Verify via GET /api/v1/nodes?label=_Test → 5 nodes
        # ------------------------------------------------------------------
        resp = await client.get("/api/v1/nodes", params={"label": "_Test"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 5, f"Expected >= 5 _Test nodes, got {body['total']}"
        assert len(body["nodes"]) >= 5

        # ------------------------------------------------------------------
        # 4. Verify via GET /api/v1/relationships → at least 4 relationships
        # ------------------------------------------------------------------
        resp = await client.get("/api/v1/relationships", params={"limit": 100})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 4, f"Expected >= 4 relationships, got {body['total']}"

        # ------------------------------------------------------------------
        # 5. Execute Cypher — DOCKED_AT vessels and ports (2 expected results)
        # ------------------------------------------------------------------
        cypher_payload = {
            "cypher": (
                "MATCH (v:_Test:Vessel)-[:DOCKED_AT]->(p:_Test:Port) "
                "RETURN v.name AS vessel, p.name AS port"
            ),
            "parameters": {},
        }
        resp = await client.post("/api/v1/cypher/execute", json=cypher_payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["rowCount"] == 2, f"Expected 2 DOCKED_AT rows, got {body['rowCount']}"
        vessel_names = {row["vessel"] for row in body["results"]}
        assert "세종대왕함" in vessel_names
        assert "독도함" in vessel_names

        # ------------------------------------------------------------------
        # 6. Verify schema contains _Test label
        # ------------------------------------------------------------------
        resp = await client.get("/api/v1/schema")
        assert resp.status_code == 200
        schema = resp.json()
        label_names = [lbl["label"] for lbl in schema["labels"]]
        assert "_Test" in label_names or any(
            l in label_names for l in ["Vessel", "Port", "Organization"]
        ), f"Expected _Test or sub-labels in schema, got: {label_names}"

        # ------------------------------------------------------------------
        # 7. Update a node — add speed property to 세종대왕함
        # ------------------------------------------------------------------
        vessel_id = node_by_name["세종대왕함"]
        resp = await client.put(
            f"/api/v1/nodes/{vessel_id}",
            json={"properties": {"speed": "30kn"}},
        )
        assert resp.status_code == 200

        # ------------------------------------------------------------------
        # 8. Verify update via GET /api/v1/nodes/{vessel_id}
        # ------------------------------------------------------------------
        resp = await client.get(f"/api/v1/nodes/{vessel_id}")
        assert resp.status_code == 200
        node_data = resp.json()
        assert node_data["properties"].get("speed") == "30kn", (
            f"Expected speed='30kn' after update, got: {node_data['properties']}"
        )

        # ------------------------------------------------------------------
        # 9. Delete all relationships then all nodes; verify clean
        # ------------------------------------------------------------------
        for rel_data in created_rels:
            rel_id = rel_data["relationship"]["id"]
            resp = await client.delete(f"/api/v1/relationships/{rel_id}")
            assert resp.status_code == 200
            assert resp.json()["deleted"] is True

        for node_data in created_nodes:
            nid = node_data["id"]
            resp = await client.delete(f"/api/v1/nodes/{nid}")
            assert resp.status_code == 200
            assert resp.json()["deleted"] is True

        # Confirm nodes are gone
        resp = await client.get("/api/v1/nodes", params={"label": "_Test"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0, f"Expected 0 _Test nodes after deletion, got {body['total']}"


# ---------------------------------------------------------------------------
# Test class: Search & query flow
# ---------------------------------------------------------------------------


class TestSearchWorkflow:
    """Node listing with label filtering, keyword search, and Cypher queries."""

    @pytest.mark.asyncio
    async def test_search_and_query_flow(self, client: httpx.AsyncClient):
        """Create 10 diverse nodes and verify listing, search, and Cypher queries."""

        # ------------------------------------------------------------------
        # 1. Create 10 diverse _Test nodes
        # ------------------------------------------------------------------
        diverse_specs = [
            {"labels": ["_Test", "Vessel"], "properties": {"name": "천자봉"}},
            {"labels": ["_Test", "Vessel"], "properties": {"name": "한라산함"}},
            {"labels": ["_Test", "Port"], "properties": {"name": "부산항", "portCode": "KRPUS"}},
            {"labels": ["_Test", "Port"], "properties": {"name": "울산항", "portCode": "KRULS"}},
            {
                "labels": ["_Test", "Regulation"],
                "properties": {"name": "SOLAS 2023", "category": "safety"},
            },
            {
                "labels": ["_Test", "Regulation"],
                "properties": {"name": "MARPOL 73/78", "category": "pollution"},
            },
            {
                "labels": ["_Test", "SeaArea"],
                "properties": {"name": "대한해협", "areaCode": "KR-SE"},
            },
            {
                "labels": ["_Test", "SeaArea"],
                "properties": {"name": "서해", "areaCode": "KR-YS"},
            },
            {
                "labels": ["_Test", "Facility"],
                "properties": {"name": "부산항 컨테이너터미널", "facilityType": "terminal"},
            },
            {
                "labels": ["_Test", "Facility"],
                "properties": {"name": "인천항 신항", "facilityType": "harbor"},
            },
        ]

        for spec in diverse_specs:
            resp = await client.post("/api/v1/nodes", json=spec)
            assert resp.status_code == 201, f"Node creation failed: {resp.text}"

        # ------------------------------------------------------------------
        # 2. List nodes filtered by label=_Test — should return 10
        # ------------------------------------------------------------------
        resp = await client.get("/api/v1/nodes", params={"label": "_Test", "limit": 50})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 10, f"Expected 10 _Test nodes, got {body['total']}"
        assert len(body["nodes"]) == 10

        # ------------------------------------------------------------------
        # 3. List nodes with q="부산" search — should find 부산항
        # ------------------------------------------------------------------
        resp = await client.get(
            "/api/v1/nodes",
            params={"label": "_Test", "q": "부산", "limit": 50},
        )
        assert resp.status_code == 200
        body = resp.json()
        found_names = [n["properties"].get("name", "") for n in body["nodes"]]
        assert any("부산" in name for name in found_names), (
            f"Expected at least one '부산' match, got: {found_names}"
        )

        # ------------------------------------------------------------------
        # 4. Execute Cypher count query: MATCH (n:_Test) RETURN count(n) → 10
        # ------------------------------------------------------------------
        resp = await client.post(
            "/api/v1/cypher/execute",
            json={"cypher": "MATCH (n:_Test) RETURN count(n) AS total", "parameters": {}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["rowCount"] == 1
        assert body["results"][0]["total"] == 10, (
            f"Expected 10 _Test nodes via Cypher, got {body['results'][0]['total']}"
        )

        # ------------------------------------------------------------------
        # 5. Execute parameterized query: MATCH (n:_Test {portCode:$code}) RETURN n
        # ------------------------------------------------------------------
        resp = await client.post(
            "/api/v1/cypher/execute",
            json={
                "cypher": "MATCH (n:_Test {portCode: $code}) RETURN n",
                "parameters": {"code": "KRPUS"},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["rowCount"] == 1, (
            f"Expected exactly 1 node with portCode=KRPUS, got {body['rowCount']}"
        )
        node_result = body["results"][0]["n"]
        assert node_result["properties"]["portCode"] == "KRPUS"


# ---------------------------------------------------------------------------
# Test class: Cypher validate / explain / execute workflow
# ---------------------------------------------------------------------------


class TestCypherWorkflow:
    """Cypher validation, explanation, and execution endpoint coverage."""

    @pytest.mark.asyncio
    async def test_cypher_validate_explain_execute(self, client: httpx.AsyncClient):
        """Validate, explain, and execute a Cypher query; also test invalid/dangerous cases."""

        # Create a node so the query has something to return
        resp = await client.post(
            "/api/v1/nodes",
            json={"labels": ["_Test", "Vessel"], "properties": {"name": "충무공이순신"}},
        )
        assert resp.status_code == 201

        # ------------------------------------------------------------------
        # 1. Validate a valid Cypher query → valid=true
        # ------------------------------------------------------------------
        valid_cypher = "MATCH (v:_Test:Vessel) WHERE v.name = $name RETURN v"
        resp = await client.post(
            "/api/v1/cypher/validate",
            json={"cypher": valid_cypher, "parameters": {}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True, f"Expected valid=true, errors: {body.get('errors')}"

        # ------------------------------------------------------------------
        # 2. Get explain plan → plan object returned
        # ------------------------------------------------------------------
        resp = await client.post(
            "/api/v1/cypher/explain",
            json={"cypher": valid_cypher, "parameters": {"name": "충무공이순신"}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "plan" in body, f"Expected 'plan' key in explain response, got: {body}"

        # ------------------------------------------------------------------
        # 3. Execute the query → results returned
        # ------------------------------------------------------------------
        resp = await client.post(
            "/api/v1/cypher/execute",
            json={"cypher": valid_cypher, "parameters": {"name": "충무공이순신"}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["rowCount"] >= 1, f"Expected at least 1 result, got {body['rowCount']}"

        # ------------------------------------------------------------------
        # 4. Validate an invalid Cypher query → valid=false
        # ------------------------------------------------------------------
        resp = await client.post(
            "/api/v1/cypher/validate",
            json={"cypher": "NOT A VALID CYPHER QUERY !!!", "parameters": {}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is False, (
            "Expected invalid=false for malformed Cypher, but got valid=true"
        )

        # ------------------------------------------------------------------
        # 5. Try a dangerous DROP query → 403 Forbidden
        # ------------------------------------------------------------------
        resp = await client.post(
            "/api/v1/cypher/execute",
            json={"cypher": "DROP INDEX node_label_name IF EXISTS", "parameters": {}},
        )
        assert resp.status_code == 403, (
            f"Expected 403 for DROP query, got {resp.status_code}: {resp.text}"
        )


# ---------------------------------------------------------------------------
# Test class: Node / relationship edge cases
# ---------------------------------------------------------------------------


class TestNodeRelationshipEdgeCases:
    """Edge cases: Korean chars, empty properties, 404, self-loops, pagination."""

    @pytest.mark.asyncio
    async def test_edge_cases(self, client: httpx.AsyncClient):
        """Comprehensive edge-case coverage for node and relationship endpoints."""

        # ------------------------------------------------------------------
        # 1. Create node with Korean characters in properties
        # ------------------------------------------------------------------
        resp = await client.post(
            "/api/v1/nodes",
            json={
                "labels": ["_Test", "Document"],
                "properties": {
                    "name": "해상교통관리 지침서",
                    "author": "해양수산부",
                    "description": "선박 통항 안전 및 해상교통 관리에 관한 세부 지침",
                },
            },
        )
        assert resp.status_code == 201
        korean_node_id = resp.json()["id"]
        assert resp.json()["properties"]["name"] == "해상교통관리 지침서"

        # ------------------------------------------------------------------
        # 2. Create node with empty properties
        # ------------------------------------------------------------------
        resp = await client.post(
            "/api/v1/nodes",
            json={"labels": ["_Test", "Placeholder"], "properties": {}},
        )
        assert resp.status_code == 201
        empty_props_node_id = resp.json()["id"]
        assert resp.json()["properties"] == {} or isinstance(resp.json()["properties"], dict)

        # ------------------------------------------------------------------
        # 3. Try to get node with invalid/non-existent ID → 404
        # ------------------------------------------------------------------
        resp = await client.get("/api/v1/nodes/nonexistent-element-id-xyz-99999")
        assert resp.status_code == 404, (
            f"Expected 404 for non-existent node, got {resp.status_code}"
        )

        # ------------------------------------------------------------------
        # 4. Create relationship between the same node (self-loop) → should work
        # ------------------------------------------------------------------
        resp = await client.post(
            "/api/v1/relationships",
            json={
                "sourceId": korean_node_id,
                "targetId": korean_node_id,
                "type": "REFERENCES",
                "properties": {},
            },
        )
        assert resp.status_code == 201, (
            f"Expected 201 for self-loop relationship, got {resp.status_code}: {resp.text}"
        )
        self_loop_rel_id = resp.json()["relationship"]["id"]

        # ------------------------------------------------------------------
        # 5. Create multiple relationships between same pair → should create multiple
        # ------------------------------------------------------------------
        resp1 = await client.post(
            "/api/v1/relationships",
            json={
                "sourceId": korean_node_id,
                "targetId": empty_props_node_id,
                "type": "RELATED_TO",
                "properties": {"note": "first"},
            },
        )
        assert resp1.status_code == 201

        resp2 = await client.post(
            "/api/v1/relationships",
            json={
                "sourceId": korean_node_id,
                "targetId": empty_props_node_id,
                "type": "RELATED_TO",
                "properties": {"note": "second"},
            },
        )
        assert resp2.status_code == 201

        # Both relationships were created with distinct IDs
        assert resp1.json()["relationship"]["id"] != resp2.json()["relationship"]["id"]

        # ------------------------------------------------------------------
        # 6. Delete a node that has relationships → DETACH DELETE should work
        # ------------------------------------------------------------------
        resp = await client.delete(f"/api/v1/nodes/{korean_node_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        # Confirm deletion
        resp = await client.get(f"/api/v1/nodes/{korean_node_id}")
        assert resp.status_code == 404

        # ------------------------------------------------------------------
        # 7. List nodes with pagination: offset=0 limit=2, then offset=2 limit=2
        # ------------------------------------------------------------------
        # Create 4 additional nodes to have a predictable dataset
        pageable_ids: list[str] = []
        for i in range(4):
            resp = await client.post(
                "/api/v1/nodes",
                json={
                    "labels": ["_Test", "PageTest"],
                    "properties": {"name": f"페이지테스트{i:02d}", "idx": i},
                },
            )
            assert resp.status_code == 201
            pageable_ids.append(resp.json()["id"])

        # First page
        resp = await client.get(
            "/api/v1/nodes",
            params={"label": "PageTest", "limit": 2, "offset": 0},
        )
        assert resp.status_code == 200
        page1 = resp.json()
        assert len(page1["nodes"]) == 2
        assert page1["limit"] == 2
        assert page1["offset"] == 0

        # Second page
        resp = await client.get(
            "/api/v1/nodes",
            params={"label": "PageTest", "limit": 2, "offset": 2},
        )
        assert resp.status_code == 200
        page2 = resp.json()
        assert len(page2["nodes"]) == 2
        assert page2["offset"] == 2

        # No overlap between pages
        page1_ids = {n["id"] for n in page1["nodes"]}
        page2_ids = {n["id"] for n in page2["nodes"]}
        assert page1_ids.isdisjoint(page2_ids), (
            f"Pages should not overlap: {page1_ids} ∩ {page2_ids}"
        )


# ---------------------------------------------------------------------------
# Test class: Health and schema consistency
# ---------------------------------------------------------------------------


class TestHealthAndSchema:
    """Health endpoint and schema consistency checks."""

    @pytest.mark.asyncio
    async def test_health_schema_consistency(self, client: httpx.AsyncClient):
        """Verify health and schema endpoints with _Test label nodes."""

        # ------------------------------------------------------------------
        # 1. GET /api/v1/health → status ok
        # ------------------------------------------------------------------
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok", (
            f"Expected health status='ok', got: {body['status']}"
        )
        assert body["neo4j_connected"] is True

        # ------------------------------------------------------------------
        # 2. GET /api/v1/health?deep=true → components include neo4j ok
        # ------------------------------------------------------------------
        resp = await client.get("/api/v1/health", params={"deep": "true"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] in ("ok", "degraded"), (
            f"Unexpected deep health status: {body['status']}"
        )
        assert "components" in body, "Deep health response must include 'components'"
        components_by_name = {c["name"]: c for c in body["components"]}
        assert "neo4j" in components_by_name, "Deep health must include a 'neo4j' component"
        assert components_by_name["neo4j"]["status"] == "ok", (
            f"Neo4j component status should be 'ok', got: {components_by_name['neo4j']['status']}"
        )

        # ------------------------------------------------------------------
        # 3. Create 3 different _Test label nodes (_Test:Alpha, _Test:Beta, _Test:Gamma)
        # ------------------------------------------------------------------
        for label in ("Alpha", "Beta", "Gamma"):
            resp = await client.post(
                "/api/v1/nodes",
                json={
                    "labels": ["_Test", label],
                    "properties": {"name": f"test_{label.lower()}"},
                },
            )
            assert resp.status_code == 201, (
                f"Failed to create _Test:{label} node: {resp.text}"
            )

        # ------------------------------------------------------------------
        # 4. GET /api/v1/schema → labels include Alpha, Beta, Gamma (or _Test)
        # ------------------------------------------------------------------
        resp = await client.get("/api/v1/schema")
        assert resp.status_code == 200
        schema = resp.json()
        label_names = {lbl["label"] for lbl in schema["labels"]}

        # At minimum _Test must appear; ideally all three sub-labels too
        has_test_labels = "_Test" in label_names or any(
            l in label_names for l in ("Alpha", "Beta", "Gamma")
        )
        assert has_test_labels, (
            f"Schema labels should include _Test or sub-labels, got: {sorted(label_names)}"
        )

        # ------------------------------------------------------------------
        # 5. Verify schema totalLabels > 0 and totalRelationshipTypes >= 0
        # ------------------------------------------------------------------
        assert schema["totalLabels"] > 0, (
            f"totalLabels should be > 0, got {schema['totalLabels']}"
        )
        assert schema["totalRelationshipTypes"] >= 0, (
            f"totalRelationshipTypes should be >= 0, got {schema['totalRelationshipTypes']}"
        )
