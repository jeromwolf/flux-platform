"""E2E harness tests -- full maritime workflow using MockNeo4jSession.

Mirrors tests/e2e/test_e2e_api_workflow.py but uses mock sessions instead
of a real Neo4j instance. Each test configures side-effects to simulate
the expected Neo4j responses for the complete workflow.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport

from tests.helpers.mock_neo4j import (
    FakeNode,
    FakeRelationship,
    MockNeo4jSession,
    MockNeo4jResult,
    make_neo4j_node,
    make_neo4j_relationship,
    build_node_record,
    build_node_record_ab,
    build_rel_record,
    count_record,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.asyncio,
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def harness():
    """Async HTTPX client backed by MockNeo4jSession."""
    from kg.config import AppConfig, Neo4jConfig, reset, set_config
    from kg.api.app import create_app
    from kg.api.deps import get_async_neo4j_session

    config = AppConfig(env="development", neo4j=Neo4jConfig(uri="bolt://mock:7687"))

    with patch("kg.api.app.get_config", return_value=config), \
         patch("kg.api.app.set_config"):
        app = create_app(config=config)

    session = MockNeo4jSession()

    async def _override():
        yield session

    app.dependency_overrides[get_async_neo4j_session] = _override

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, session

    reset()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _reset(session: MockNeo4jSession, side_effects: list[Any]) -> None:
    """Replace session side-effects and reset the call index."""
    session._side_effects = side_effects
    session._call_index = 0


# ===========================================================================
# 1. TestMaritimeGraphWorkflowHarness
# ===========================================================================


class TestMaritimeGraphWorkflowHarness:
    """Full lifecycle: create 5 nodes, 4 relationships, query, update, delete."""

    async def test_full_maritime_graph_lifecycle(self, harness: Any) -> None:
        """End-to-end lifecycle for a small maritime knowledge graph (harness)."""
        client, session = harness

        # -- Step 1: Create 5 nodes ----------------------------------------
        node_specs = [
            (["_Test", "Vessel"], {"name": "세종대왕함", "vesselType": "DDG", "displacement": "7600t"}),
            (["_Test", "Vessel"], {"name": "독도함", "vesselType": "LPH", "displacement": "18800t"}),
            (["_Test", "Port"], {"name": "부산항", "portCode": "KRPUS", "country": "대한민국"}),
            (["_Test", "Port"], {"name": "인천항", "portCode": "KRICN", "country": "대한민국"}),
            (["_Test", "Organization"], {"name": "KRISO", "fullName": "한국해양과학기술원"}),
        ]

        created_nodes: list[dict[str, Any]] = []
        for i, (labels, props) in enumerate(node_specs):
            node = make_neo4j_node(element_id=f"4:test:{i}", labels=labels, props=props)
            _reset(session, [MockNeo4jResult([build_node_record(node)])])

            resp = await client.post(
                "/api/v1/nodes",
                json={"labels": labels, "properties": props},
            )
            assert resp.status_code == 201, f"Node creation failed: {resp.text}"
            data = resp.json()
            assert data["id"], "Response must include element ID"
            created_nodes.append(data)

        node_by_name: dict[str, str] = {
            n["properties"]["name"]: n["id"] for n in created_nodes
        }
        assert "세종대왕함" in node_by_name
        assert "독도함" in node_by_name
        assert "부산항" in node_by_name
        assert "인천항" in node_by_name
        assert "KRISO" in node_by_name

        # -- Step 2: Create 4 relationships ---------------------------------
        rel_specs = [
            ("세종대왕함", "부산항", "DOCKED_AT"),
            ("독도함", "인천항", "DOCKED_AT"),
            ("KRISO", "세종대왕함", "OPERATES"),
            ("KRISO", "독도함", "OPERATES"),
        ]

        created_rels: list[dict[str, Any]] = []
        for j, (src_name, tgt_name, rel_type) in enumerate(rel_specs):
            src_id = node_by_name[src_name]
            tgt_id = node_by_name[tgt_name]
            src_node = make_neo4j_node(
                element_id=src_id,
                labels=["_Test"],
                props={"name": src_name},
            )
            tgt_node = make_neo4j_node(
                element_id=tgt_id,
                labels=["_Test"],
                props={"name": tgt_name},
            )
            rel = make_neo4j_relationship(
                element_id=f"5:test:{j}",
                rel_type=rel_type,
                src_id=src_id,
                tgt_id=tgt_id,
            )
            record = build_node_record_ab(src_node, rel, tgt_node)
            _reset(session, [MockNeo4jResult([record])])

            resp = await client.post(
                "/api/v1/relationships",
                json={
                    "sourceId": src_id,
                    "targetId": tgt_id,
                    "type": rel_type,
                    "properties": {},
                },
            )
            assert resp.status_code == 201, f"Relationship creation failed: {resp.text}"
            data = resp.json()
            assert data["relationship"]["id"], "Response must include relationship ID"
            created_rels.append(data)

        # -- Step 3: GET /api/v1/nodes?label=_Test -> 5 nodes ---------------
        all_node_records = [
            build_node_record(
                make_neo4j_node(
                    element_id=n["id"],
                    labels=n["labels"],
                    props=n["properties"],
                )
            )
            for n in created_nodes
        ]
        _reset(
            session,
            [
                MockNeo4jResult([count_record(5)]),
                MockNeo4jResult(all_node_records),
            ],
        )
        resp = await client.get("/api/v1/nodes", params={"label": "_Test"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 5, f"Expected >= 5 _Test nodes, got {body['total']}"
        assert len(body["nodes"]) >= 5

        # -- Step 4: GET /api/v1/relationships -> at least 4 ----------------
        all_rel_records = [
            build_rel_record(
                make_neo4j_relationship(
                    element_id=r["relationship"]["id"],
                    rel_type=r["relationship"]["type"],
                    src_id=r["relationship"]["sourceId"],
                    tgt_id=r["relationship"]["targetId"],
                )
            )
            for r in created_rels
        ]
        _reset(
            session,
            [
                MockNeo4jResult([count_record(4)]),
                MockNeo4jResult(all_rel_records),
            ],
        )
        resp = await client.get("/api/v1/relationships", params={"limit": 100})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 4, f"Expected >= 4 relationships, got {body['total']}"

        # -- Step 5: Execute Cypher -- DOCKED_AT vessels and ports -----------
        _reset(
            session,
            [
                MockNeo4jResult([
                    {"vessel": "세종대왕함", "port": "부산항"},
                    {"vessel": "독도함", "port": "인천항"},
                ]),
            ],
        )
        resp = await client.post(
            "/api/v1/cypher/execute",
            json={
                "cypher": (
                    "MATCH (v:_Test:Vessel)-[:DOCKED_AT]->(p:_Test:Port) "
                    "RETURN v.name AS vessel, p.name AS port"
                ),
                "parameters": {},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["rowCount"] == 2, f"Expected 2 DOCKED_AT rows, got {body['rowCount']}"
        vessel_names = {row["vessel"] for row in body["results"]}
        assert "세종대왕함" in vessel_names
        assert "독도함" in vessel_names

        # -- Step 6: GET /api/v1/schema contains _Test ----------------------
        # schema route: db.labels(), db.relationshipTypes(), then count per label
        _reset(
            session,
            [
                MockNeo4jResult([
                    {"label": "_Test"},
                    {"label": "Vessel"},
                    {"label": "Port"},
                    {"label": "Organization"},
                ]),
                MockNeo4jResult([
                    {"relationshipType": "DOCKED_AT"},
                    {"relationshipType": "OPERATES"},
                ]),
                MockNeo4jResult([{"cnt": 5}]),   # _Test count
                MockNeo4jResult([{"cnt": 2}]),   # Vessel count
                MockNeo4jResult([{"cnt": 2}]),   # Port count
                MockNeo4jResult([{"cnt": 1}]),   # Organization count
            ],
        )
        resp = await client.get("/api/v1/schema")
        assert resp.status_code == 200
        schema = resp.json()
        label_names = [lbl["label"] for lbl in schema["labels"]]
        assert "_Test" in label_names or any(
            lbl in label_names for lbl in ["Vessel", "Port", "Organization"]
        ), f"Expected _Test or sub-labels in schema, got: {label_names}"

        # -- Step 7: Update node -- add speed to 세종대왕함 ----------------
        vessel_id = node_by_name["세종대왕함"]
        updated_node = make_neo4j_node(
            element_id=vessel_id,
            labels=["_Test", "Vessel"],
            props={
                "name": "세종대왕함",
                "vesselType": "DDG",
                "displacement": "7600t",
                "speed": "30kn",
            },
        )
        _reset(session, [MockNeo4jResult([build_node_record(updated_node)])])
        resp = await client.put(
            f"/api/v1/nodes/{vessel_id}",
            json={"properties": {"speed": "30kn"}},
        )
        assert resp.status_code == 200

        # -- Step 8: Verify update via GET ----------------------------------
        _reset(session, [MockNeo4jResult([build_node_record(updated_node)])])
        resp = await client.get(f"/api/v1/nodes/{vessel_id}")
        assert resp.status_code == 200
        node_data = resp.json()
        assert node_data["properties"].get("speed") == "30kn", (
            f"Expected speed='30kn' after update, got: {node_data['properties']}"
        )

        # -- Step 9: Delete all relationships then all nodes ----------------
        for rel_data in created_rels:
            rel_id = rel_data["relationship"]["id"]
            _reset(
                session,
                [
                    MockNeo4jResult([count_record(1)]),  # existence check
                    MockNeo4jResult([]),                  # DELETE
                ],
            )
            resp = await client.delete(f"/api/v1/relationships/{rel_id}")
            assert resp.status_code == 200
            assert resp.json()["deleted"] is True

        for node_data in created_nodes:
            nid = node_data["id"]
            _reset(
                session,
                [
                    MockNeo4jResult([count_record(1)]),  # existence check
                    MockNeo4jResult([]),                  # DETACH DELETE
                ],
            )
            resp = await client.delete(f"/api/v1/nodes/{nid}")
            assert resp.status_code == 200
            assert resp.json()["deleted"] is True

        # -- Confirm nodes are gone -----------------------------------------
        _reset(
            session,
            [
                MockNeo4jResult([count_record(0)]),
                MockNeo4jResult([]),
            ],
        )
        resp = await client.get("/api/v1/nodes", params={"label": "_Test"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0, f"Expected 0 _Test nodes after deletion, got {body['total']}"


# ===========================================================================
# 2. TestSearchWorkflowHarness
# ===========================================================================


class TestSearchWorkflowHarness:
    """Node listing with label filtering, keyword search, and Cypher queries (harness)."""

    async def test_search_and_query_flow(self, harness: Any) -> None:
        """Create 10 diverse nodes and verify listing, search, and Cypher queries."""
        client, session = harness

        # -- Step 1: Create 10 diverse _Test nodes --------------------------
        diverse_specs = [
            (["_Test", "Vessel"], {"name": "천자봉"}),
            (["_Test", "Vessel"], {"name": "한라산함"}),
            (["_Test", "Port"], {"name": "부산항", "portCode": "KRPUS"}),
            (["_Test", "Port"], {"name": "울산항", "portCode": "KRULS"}),
            (["_Test", "Regulation"], {"name": "SOLAS 2023", "category": "safety"}),
            (["_Test", "Regulation"], {"name": "MARPOL 73/78", "category": "pollution"}),
            (["_Test", "SeaArea"], {"name": "대한해협", "areaCode": "KR-SE"}),
            (["_Test", "SeaArea"], {"name": "서해", "areaCode": "KR-YS"}),
            (["_Test", "Facility"], {"name": "부산항 컨테이너터미널", "facilityType": "terminal"}),
            (["_Test", "Facility"], {"name": "인천항 신항", "facilityType": "harbor"}),
        ]

        created_nodes: list[dict[str, Any]] = []
        for i, (labels, props) in enumerate(diverse_specs):
            node = make_neo4j_node(element_id=f"4:test:{i}", labels=labels, props=props)
            _reset(session, [MockNeo4jResult([build_node_record(node)])])

            resp = await client.post(
                "/api/v1/nodes",
                json={"labels": labels, "properties": props},
            )
            assert resp.status_code == 201, f"Node creation failed: {resp.text}"
            created_nodes.append(resp.json())

        # -- Step 2: List nodes label=_Test -> 10 ---------------------------
        all_records = [
            build_node_record(
                make_neo4j_node(
                    element_id=n["id"],
                    labels=n["labels"],
                    props=n["properties"],
                )
            )
            for n in created_nodes
        ]
        _reset(
            session,
            [
                MockNeo4jResult([count_record(10)]),
                MockNeo4jResult(all_records),
            ],
        )
        resp = await client.get("/api/v1/nodes", params={"label": "_Test", "limit": 50})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 10, f"Expected 10 _Test nodes, got {body['total']}"
        assert len(body["nodes"]) == 10

        # -- Step 3: Search q="부산" ----------------------------------------
        # _Test has no fulltext index -> CONTAINS fallback path
        busan_nodes = [n for n in created_nodes if "부산" in n["properties"].get("name", "")]
        busan_records = [
            build_node_record(
                make_neo4j_node(
                    element_id=n["id"],
                    labels=n["labels"],
                    props=n["properties"],
                )
            )
            for n in busan_nodes
        ]
        _reset(
            session,
            [
                MockNeo4jResult([count_record(len(busan_nodes))]),
                MockNeo4jResult(busan_records),
            ],
        )
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

        # -- Step 4: Cypher count query -> 10 -------------------------------
        _reset(session, [MockNeo4jResult([{"total": 10}])])
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

        # -- Step 5: Parameterized query -> portCode=KRPUS -----------------
        port_node = make_neo4j_node(
            element_id="4:test:2",
            labels=["_Test", "Port"],
            props={"name": "부산항", "portCode": "KRPUS"},
        )
        _reset(session, [MockNeo4jResult([{"n": port_node}])])
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


# ===========================================================================
# 3. TestCypherWorkflowHarness
# ===========================================================================


class TestCypherWorkflowHarness:
    """Cypher validation, explanation, and execution endpoint coverage (harness)."""

    async def test_cypher_validate_explain_execute(self, harness: Any) -> None:
        """Validate, explain, and execute a Cypher query; test invalid/dangerous cases."""
        client, session = harness

        # -- Create a node so the query has data ----------------------------
        node = make_neo4j_node(
            element_id="4:test:0",
            labels=["_Test", "Vessel"],
            props={"name": "충무공이순신"},
        )
        _reset(session, [MockNeo4jResult([build_node_record(node)])])
        resp = await client.post(
            "/api/v1/nodes",
            json={"labels": ["_Test", "Vessel"], "properties": {"name": "충무공이순신"}},
        )
        assert resp.status_code == 201

        # -- 1. Validate valid Cypher -> valid=true -------------------------
        # Validate is pure logic (no session.run)
        valid_cypher = "MATCH (v:_Test:Vessel) WHERE v.name = $name RETURN v"
        resp = await client.post(
            "/api/v1/cypher/validate",
            json={"cypher": valid_cypher, "parameters": {}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True, f"Expected valid=true, errors: {body.get('errors')}"

        # -- 2. Explain plan ------------------------------------------------
        # explain route: session.run("EXPLAIN ...") -> records + result.consume()
        _reset(session, [MockNeo4jResult([])])
        resp = await client.post(
            "/api/v1/cypher/explain",
            json={"cypher": valid_cypher, "parameters": {"name": "충무공이순신"}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "plan" in body, f"Expected 'plan' key in explain response, got: {body}"

        # -- 3. Execute the query -> results --------------------------------
        _reset(session, [MockNeo4jResult([{"v": node}])])
        resp = await client.post(
            "/api/v1/cypher/execute",
            json={"cypher": valid_cypher, "parameters": {"name": "충무공이순신"}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["rowCount"] >= 1, f"Expected at least 1 result, got {body['rowCount']}"

        # -- 4. Validate invalid Cypher -> valid=false ----------------------
        resp = await client.post(
            "/api/v1/cypher/validate",
            json={"cypher": "NOT A VALID CYPHER QUERY !!!", "parameters": {}},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is False, (
            "Expected valid=false for malformed Cypher, but got valid=true"
        )

        # -- 5. Dangerous DROP -> 403 Forbidden (pure logic, no session) ----
        resp = await client.post(
            "/api/v1/cypher/execute",
            json={"cypher": "DROP INDEX node_label_name IF EXISTS", "parameters": {}},
        )
        assert resp.status_code == 403, (
            f"Expected 403 for DROP query, got {resp.status_code}: {resp.text}"
        )


# ===========================================================================
# 4. TestNodeRelationshipEdgeCasesHarness
# ===========================================================================


class TestNodeRelationshipEdgeCasesHarness:
    """Edge cases: Korean chars, empty props, 404, self-loops, pagination (harness)."""

    async def test_edge_cases(self, harness: Any) -> None:
        """Comprehensive edge-case coverage for node and relationship endpoints."""
        client, session = harness

        # -- 1. Korean characters in properties -----------------------------
        korean_node = make_neo4j_node(
            element_id="4:test:0",
            labels=["_Test", "Document"],
            props={
                "name": "해상교통관리 지침서",
                "author": "해양수산부",
                "description": "선박 통항 안전 및 해상교통 관리에 관한 세부 지침",
            },
        )
        _reset(session, [MockNeo4jResult([build_node_record(korean_node)])])
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

        # -- 2. Empty properties node ---------------------------------------
        empty_node = make_neo4j_node(
            element_id="4:test:1",
            labels=["_Test", "Placeholder"],
            props={},
        )
        _reset(session, [MockNeo4jResult([build_node_record(empty_node)])])
        resp = await client.post(
            "/api/v1/nodes",
            json={"labels": ["_Test", "Placeholder"], "properties": {}},
        )
        assert resp.status_code == 201
        empty_props_node_id = resp.json()["id"]
        assert resp.json()["properties"] == {} or isinstance(resp.json()["properties"], dict)

        # -- 3. Non-existent node -> 404 ------------------------------------
        _reset(session, [MockNeo4jResult([])])
        resp = await client.get("/api/v1/nodes/nonexistent-element-id-xyz-99999")
        assert resp.status_code == 404, (
            f"Expected 404 for non-existent node, got {resp.status_code}"
        )

        # -- 4. Self-loop relationship --------------------------------------
        src_node = make_neo4j_node(
            element_id=korean_node_id,
            labels=["_Test", "Document"],
            props={"name": "해상교통관리 지침서"},
        )
        self_rel = make_neo4j_relationship(
            element_id="5:test:0",
            rel_type="REFERENCES",
            src_id=korean_node_id,
            tgt_id=korean_node_id,
        )
        record = build_node_record_ab(src_node, self_rel, src_node)
        _reset(session, [MockNeo4jResult([record])])
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

        # -- 5. Multiple relationships between same pair --------------------
        tgt_node = make_neo4j_node(
            element_id=empty_props_node_id,
            labels=["_Test", "Placeholder"],
            props={},
        )

        rel1 = make_neo4j_relationship(
            element_id="5:test:1",
            rel_type="RELATED_TO",
            src_id=korean_node_id,
            tgt_id=empty_props_node_id,
            props={"note": "first"},
        )
        record1 = build_node_record_ab(src_node, rel1, tgt_node)
        _reset(session, [MockNeo4jResult([record1])])
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

        rel2 = make_neo4j_relationship(
            element_id="5:test:2",
            rel_type="RELATED_TO",
            src_id=korean_node_id,
            tgt_id=empty_props_node_id,
            props={"note": "second"},
        )
        record2 = build_node_record_ab(src_node, rel2, tgt_node)
        _reset(session, [MockNeo4jResult([record2])])
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
        assert resp1.json()["relationship"]["id"] != resp2.json()["relationship"]["id"]

        # -- 6. Delete a node that has relationships -> DETACH DELETE --------
        _reset(
            session,
            [
                MockNeo4jResult([count_record(1)]),  # existence check
                MockNeo4jResult([]),                  # DETACH DELETE
            ],
        )
        resp = await client.delete(f"/api/v1/nodes/{korean_node_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

        # Confirm deletion
        _reset(session, [MockNeo4jResult([])])
        resp = await client.get(f"/api/v1/nodes/{korean_node_id}")
        assert resp.status_code == 404

        # -- 7. Pagination: offset=0 limit=2, then offset=2 limit=2 --------
        pageable_nodes = []
        for i in range(4):
            pn = make_neo4j_node(
                element_id=f"4:test:page{i}",
                labels=["_Test", "PageTest"],
                props={"name": f"페이지테스트{i:02d}", "idx": i},
            )
            _reset(session, [MockNeo4jResult([build_node_record(pn)])])
            resp = await client.post(
                "/api/v1/nodes",
                json={
                    "labels": ["_Test", "PageTest"],
                    "properties": {"name": f"페이지테스트{i:02d}", "idx": i},
                },
            )
            assert resp.status_code == 201
            pageable_nodes.append(resp.json())

        # First page
        page1_records = [
            build_node_record(
                make_neo4j_node(
                    element_id=pageable_nodes[i]["id"],
                    labels=pageable_nodes[i]["labels"],
                    props=pageable_nodes[i]["properties"],
                )
            )
            for i in range(2)
        ]
        _reset(
            session,
            [
                MockNeo4jResult([count_record(4)]),
                MockNeo4jResult(page1_records),
            ],
        )
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
        page2_records = [
            build_node_record(
                make_neo4j_node(
                    element_id=pageable_nodes[i]["id"],
                    labels=pageable_nodes[i]["labels"],
                    props=pageable_nodes[i]["properties"],
                )
            )
            for i in range(2, 4)
        ]
        _reset(
            session,
            [
                MockNeo4jResult([count_record(4)]),
                MockNeo4jResult(page2_records),
            ],
        )
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
            f"Pages should not overlap: {page1_ids} & {page2_ids}"
        )


# ===========================================================================
# 5. TestHealthAndSchemaHarness
# ===========================================================================


class TestHealthAndSchemaHarness:
    """Health endpoint and schema consistency checks (harness)."""

    async def test_health_schema_consistency(self, harness: Any) -> None:
        """Verify health and schema endpoints with _Test label nodes."""
        client, session = harness

        # -- 1. GET /api/v1/health -> status ok -----------------------------
        _reset(session, [MockNeo4jResult([{"n": 1}])])
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok", (
            f"Expected health status='ok', got: {body['status']}"
        )
        assert body["neo4j_connected"] is True

        # -- 2. GET /api/v1/health?deep=true -> components ------------------
        _reset(session, [MockNeo4jResult([{"n": 1}])])
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

        # -- 3. Create 3 _Test label nodes (Alpha, Beta, Gamma) ------------
        for idx, label in enumerate(("Alpha", "Beta", "Gamma")):
            node = make_neo4j_node(
                element_id=f"4:test:hs{idx}",
                labels=["_Test", label],
                props={"name": f"test_{label.lower()}"},
            )
            _reset(session, [MockNeo4jResult([build_node_record(node)])])
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

        # -- 4. GET /api/v1/schema -> labels include Alpha/Beta/Gamma ------
        _reset(
            session,
            [
                MockNeo4jResult([
                    {"label": "_Test"},
                    {"label": "Alpha"},
                    {"label": "Beta"},
                    {"label": "Gamma"},
                ]),
                MockNeo4jResult([]),  # no relationship types
                MockNeo4jResult([{"cnt": 3}]),  # _Test count
                MockNeo4jResult([{"cnt": 1}]),  # Alpha count
                MockNeo4jResult([{"cnt": 1}]),  # Beta count
                MockNeo4jResult([{"cnt": 1}]),  # Gamma count
            ],
        )
        resp = await client.get("/api/v1/schema")
        assert resp.status_code == 200
        schema = resp.json()
        label_names = {lbl["label"] for lbl in schema["labels"]}

        has_test_labels = "_Test" in label_names or any(
            lbl in label_names for lbl in ("Alpha", "Beta", "Gamma")
        )
        assert has_test_labels, (
            f"Schema labels should include _Test or sub-labels, got: {sorted(label_names)}"
        )

        # -- 5. Verify totalLabels > 0 and totalRelationshipTypes >= 0 -----
        assert schema["totalLabels"] > 0, (
            f"totalLabels should be > 0, got {schema['totalLabels']}"
        )
        assert schema["totalRelationshipTypes"] >= 0, (
            f"totalRelationshipTypes should be >= 0, got {schema['totalRelationshipTypes']}"
        )
