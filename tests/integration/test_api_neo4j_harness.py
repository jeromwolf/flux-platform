"""Harness version of test_api_neo4j.py — runs WITHOUT a real Neo4j instance.

All Neo4j interactions are replaced by MockNeo4jSession / MockNeo4jResult from
``tests/helpers/mock_neo4j``.  Tests are marked ``unit`` so they run in the
normal CI pipeline without any external services.
"""

from __future__ import annotations

import time
from typing import Any

import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport
from unittest.mock import patch

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

# ---------------------------------------------------------------------------
# Module-level marks: unit tests, async
# ---------------------------------------------------------------------------

pytestmark = [
    pytest.mark.unit,
    pytest.mark.asyncio,
]

# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def harness_client():
    """Async HTTPX client backed by MockNeo4jSession (no real Neo4j).

    Yields a 3-tuple ``(ac, session, app)`` where:

    - ``ac``      — :class:`httpx.AsyncClient` using ASGI transport
    - ``session`` — :class:`MockNeo4jSession` whose ``_side_effects`` and
                    ``_call_index`` can be reset before each test
    - ``app``     — the FastAPI application instance (for dependency inspection)
    """
    from kg.config import AppConfig, Neo4jConfig, reset

    config = AppConfig(env="development", neo4j=Neo4jConfig(uri="bolt://mock:7687"))

    with patch("kg.api.app.get_config", return_value=config), patch(
        "kg.api.app.set_config"
    ):
        from kg.api.app import create_app

        app = create_app(config=config)

    from kg.api.deps import get_async_neo4j_session

    session = MockNeo4jSession()

    async def _override():
        yield session

    app.dependency_overrides[get_async_neo4j_session] = _override

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, session, app

    reset()


# ---------------------------------------------------------------------------
# Helper: reset session side-effects for each test
# ---------------------------------------------------------------------------


def _reset(session: MockNeo4jSession, side_effects: list[Any]) -> None:
    """Replace session side-effects and reset the call index."""
    session._side_effects = side_effects
    session._call_index = 0


# ===========================================================================
# TestHealthEndpointHarness
# ===========================================================================


class TestHealthEndpointHarness:
    """Verify /api/v1/health using a mock Neo4j session."""

    async def test_health_returns_ok(self, harness_client: Any) -> None:
        """GET /api/v1/health returns status='ok' and neo4j_connected=true."""
        client, session, _app = harness_client
        # Health handler calls session.run("RETURN 1 AS n") then result.single()
        _reset(session, [MockNeo4jResult([{"n": 1}])])

        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "ok"
        assert body["neo4j_connected"] is True

    async def test_health_deep(self, harness_client: Any) -> None:
        """GET /api/v1/health?deep=true returns a 'components' list with neo4j."""
        client, session, _app = harness_client
        _reset(session, [MockNeo4jResult([{"n": 1}])])

        resp = await client.get("/api/v1/health", params={"deep": "true"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "components" in body
        assert isinstance(body["components"], list)
        assert len(body["components"]) > 0
        neo4j_component = next(
            (c for c in body["components"] if c["name"] == "neo4j"), None
        )
        assert neo4j_component is not None, "Expected 'neo4j' in components"
        assert neo4j_component["status"] == "ok"

    async def test_health_response_time(self, harness_client: Any) -> None:
        """Health endpoint must respond within 2 seconds."""
        client, session, _app = harness_client
        _reset(session, [MockNeo4jResult([{"n": 1}])])

        start = time.monotonic()
        resp = await client.get("/api/v1/health")
        elapsed = time.monotonic() - start
        assert resp.status_code == 200
        assert elapsed < 2.0, f"Health endpoint too slow: {elapsed:.3f}s"


# ===========================================================================
# TestNodesCRUDHarness
# ===========================================================================


class TestNodesCRUDHarness:
    """CRUD operations on /api/v1/nodes with mock Neo4j."""

    async def test_create_node(self, harness_client: Any) -> None:
        """POST /api/v1/nodes creates a node and returns 201 with id/labels."""
        client, session, _app = harness_client
        node = make_neo4j_node(
            element_id="4:test:1",
            labels=["_Test", "Vessel"],
            props={"name": "세종대왕함"},
        )
        _reset(session, [MockNeo4jResult([build_node_record(node)])])

        resp = await client.post(
            "/api/v1/nodes",
            json={"labels": ["_Test", "Vessel"], "properties": {"name": "세종대왕함"}},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert "id" in body
        assert "_Test" in body["labels"]
        assert "Vessel" in body["labels"]
        assert body["properties"].get("name") == "세종대왕함"

    async def test_get_node(self, harness_client: Any) -> None:
        """GET /api/v1/nodes/{node_id} returns 200 with correct node data."""
        client, session, _app = harness_client
        node = make_neo4j_node(
            element_id="4:test:10",
            labels=["_Test", "Vessel"],
            props={"name": "독도함"},
        )
        _reset(session, [MockNeo4jResult([build_node_record(node)])])

        resp = await client.get("/api/v1/nodes/4:test:10")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["id"] == "4:test:10"
        assert body["properties"].get("name") == "독도함"

    async def test_update_node(self, harness_client: Any) -> None:
        """PUT /api/v1/nodes/{node_id} returns 200 with merged properties."""
        client, session, _app = harness_client
        node = make_neo4j_node(
            element_id="4:test:20",
            labels=["_Test", "Vessel"],
            props={"name": "충무공함", "type": "destroyer", "active": True},
        )
        _reset(session, [MockNeo4jResult([build_node_record(node)])])

        resp = await client.put(
            "/api/v1/nodes/4:test:20",
            json={"properties": {"type": "destroyer", "active": True}},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["properties"].get("name") == "충무공함"
        assert body["properties"].get("type") == "destroyer"
        assert body["properties"].get("active") is True

    async def test_delete_node(self, harness_client: Any) -> None:
        """DELETE /api/v1/nodes/{node_id} returns {"deleted": true}."""
        client, session, _app = harness_client
        # delete_node: first call is CHECK (count), second is DELETE (no result needed)
        _reset(
            session,
            [
                MockNeo4jResult([count_record(1)]),  # existence check
                MockNeo4jResult([]),                  # DETACH DELETE
            ],
        )

        resp = await client.delete("/api/v1/nodes/4:test:30")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["deleted"] is True

    async def test_list_nodes(self, harness_client: Any) -> None:
        """GET /api/v1/nodes?label=_Test returns total >= 3 and 3 nodes."""
        client, session, _app = harness_client
        nodes = [
            make_neo4j_node(
                element_id=f"4:test:{i}",
                labels=["_Test", "Vessel"],
                props={"name": f"함정{i}"},
            )
            for i in range(3)
        ]
        _reset(
            session,
            [
                MockNeo4jResult([count_record(3)]),  # COUNT query
                MockNeo4jResult([build_node_record(n) for n in nodes]),  # list query
            ],
        )

        resp = await client.get("/api/v1/nodes", params={"label": "_Test"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] >= 3
        assert len(body["nodes"]) >= 3

    async def test_list_nodes_pagination(self, harness_client: Any) -> None:
        """GET /api/v1/nodes?label=_Test&limit=2 returns 2 nodes, total >= 5."""
        client, session, _app = harness_client
        nodes = [
            make_neo4j_node(
                element_id=f"4:test:{i}",
                labels=["_Test", "Vessel"],
                props={"name": f"페이지함{i}"},
            )
            for i in range(2)
        ]
        _reset(
            session,
            [
                MockNeo4jResult([count_record(5)]),  # COUNT query — total=5
                MockNeo4jResult([build_node_record(n) for n in nodes]),  # limit=2
            ],
        )

        resp = await client.get(
            "/api/v1/nodes", params={"label": "_Test", "limit": 2}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body["nodes"]) == 2
        assert body["total"] >= 5

    async def test_get_nonexistent_node(self, harness_client: Any) -> None:
        """GET with a fake ID that returns no records → 404."""
        client, session, _app = harness_client
        _reset(session, [MockNeo4jResult([])])  # empty → 404

        fake_id = "4:00000000-0000-0000-0000-000000000000:999999"
        resp = await client.get(f"/api/v1/nodes/{fake_id}")
        assert resp.status_code == 404, resp.text


# ===========================================================================
# TestRelationshipsCRUDHarness
# ===========================================================================


class TestRelationshipsCRUDHarness:
    """CRUD operations on /api/v1/relationships with mock Neo4j."""

    def _make_rel_triple(
        self,
        vessel_eid: str = "4:test:100",
        port_eid: str = "4:test:101",
        rel_eid: str = "5:test:1",
        rel_props: dict[str, Any] | None = None,
    ) -> tuple[FakeNode, FakeRelationship, FakeNode]:
        """Create a vessel node, rel, port node triple for tests."""
        vessel = make_neo4j_node(
            element_id=vessel_eid,
            labels=["_Test", "Vessel"],
            props={"name": "관계함"},
        )
        port = make_neo4j_node(
            element_id=port_eid,
            labels=["_Test", "Port"],
            props={"name": "인천항"},
        )
        rel = make_neo4j_relationship(
            element_id=rel_eid,
            rel_type="DOCKED_AT",
            src_id=vessel_eid,
            tgt_id=port_eid,
            props=rel_props or {},
        )
        return vessel, rel, port

    async def test_create_relationship(self, harness_client: Any) -> None:
        """POST /api/v1/relationships → 201, relationship with type DOCKED_AT."""
        client, session, _app = harness_client
        vessel, rel, port = self._make_rel_triple()
        record = build_node_record_ab(vessel, rel, port)
        _reset(session, [MockNeo4jResult([record])])

        resp = await client.post(
            "/api/v1/relationships",
            json={
                "sourceId": vessel.element_id,
                "targetId": port.element_id,
                "type": "DOCKED_AT",
                "properties": {},
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        r = body["relationship"]
        assert "id" in r
        assert r["type"] == "DOCKED_AT"
        assert r["sourceId"] == vessel.element_id
        assert r["targetId"] == port.element_id

    async def test_get_relationship(self, harness_client: Any) -> None:
        """GET /api/v1/relationships/{rel_id} → 200 with correct relationship."""
        client, session, _app = harness_client
        vessel, rel, port = self._make_rel_triple(rel_eid="5:test:42")
        record = build_node_record_ab(vessel, rel, port)
        _reset(session, [MockNeo4jResult([record])])

        resp = await client.get("/api/v1/relationships/5:test:42")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["relationship"]["id"] == "5:test:42"
        assert body["relationship"]["type"] == "DOCKED_AT"

    async def test_update_relationship(self, harness_client: Any) -> None:
        """PUT /api/v1/relationships/{rel_id} returns updated EdgeResponse."""
        client, session, _app = harness_client
        rel = make_neo4j_relationship(
            element_id="5:test:50",
            rel_type="DOCKED_AT",
            src_id="4:test:100",
            tgt_id="4:test:101",
            props={"berth": "A1", "since": "2026-01-01"},
        )
        # update_relationship returns a record keyed "r" (with a and b from startNode/endNode)
        # The route uses `_extract_relationship(record, "r")` on the result
        _reset(session, [MockNeo4jResult([build_rel_record(rel)])])

        resp = await client.put(
            "/api/v1/relationships/5:test:50",
            json={"properties": {"berth": "A1", "since": "2026-01-01"}},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["properties"].get("berth") == "A1"
        assert body["properties"].get("since") == "2026-01-01"

    async def test_delete_relationship(self, harness_client: Any) -> None:
        """DELETE /api/v1/relationships/{rel_id} returns {"deleted": true}."""
        client, session, _app = harness_client
        _reset(
            session,
            [
                MockNeo4jResult([count_record(1)]),  # existence check
                MockNeo4jResult([]),                  # DELETE
            ],
        )

        resp = await client.delete("/api/v1/relationships/5:test:60")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["deleted"] is True

    async def test_list_relationships(self, harness_client: Any) -> None:
        """GET /api/v1/relationships?type=DOCKED_AT returns total >= 3."""
        client, session, _app = harness_client
        rels = [
            make_neo4j_relationship(
                element_id=f"5:test:{i}",
                rel_type="DOCKED_AT",
                src_id=f"4:test:{i * 2}",
                tgt_id=f"4:test:{i * 2 + 1}",
            )
            for i in range(3)
        ]
        _reset(
            session,
            [
                MockNeo4jResult([count_record(3)]),  # COUNT
                MockNeo4jResult([build_rel_record(r) for r in rels]),  # list
            ],
        )

        resp = await client.get(
            "/api/v1/relationships", params={"type": "DOCKED_AT"}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] >= 3


# ===========================================================================
# TestSchemaEndpointHarness
# ===========================================================================


class TestSchemaEndpointHarness:
    """Schema introspection endpoint with mock Neo4j."""

    async def test_schema_returns_labels(self, harness_client: Any) -> None:
        """GET /api/v1/schema includes '_Test' label in labels list."""
        client, session, _app = harness_client
        # schema route runs 3 queries in sequence:
        # 1. CALL db.labels() → list of {label: str}
        # 2. CALL db.relationshipTypes() → list of {relationshipType: str}
        # 3. One MATCH count per label (we have 1 label here)
        label_records = [{"label": "_Test"}]
        rel_type_records = [{"relationshipType": "DOCKED_AT"}]
        count_records = [{"cnt": 1}]  # count for _Test
        _reset(
            session,
            [
                MockNeo4jResult(label_records),
                MockNeo4jResult(rel_type_records),
                MockNeo4jResult(count_records),  # count for _Test label
            ],
        )

        resp = await client.get("/api/v1/schema")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "labels" in body
        label_names = [entry["label"] for entry in body["labels"]]
        assert "_Test" in label_names, f"'_Test' not found in labels: {label_names}"

    async def test_schema_returns_relationship_types(
        self, harness_client: Any
    ) -> None:
        """GET /api/v1/schema includes DOCKED_AT in relationshipTypes."""
        client, session, _app = harness_client
        label_records = [{"label": "Vessel"}, {"label": "Port"}]
        rel_type_records = [{"relationshipType": "DOCKED_AT"}]
        # One count query per label
        _reset(
            session,
            [
                MockNeo4jResult(label_records),
                MockNeo4jResult(rel_type_records),
                MockNeo4jResult([{"cnt": 2}]),   # count for Vessel
                MockNeo4jResult([{"cnt": 1}]),   # count for Port
            ],
        )

        resp = await client.get("/api/v1/schema")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "relationshipTypes" in body
        assert "DOCKED_AT" in body["relationshipTypes"], (
            f"DOCKED_AT not in {body['relationshipTypes']}"
        )


# ===========================================================================
# TestCypherEndpointHarness
# ===========================================================================


class TestCypherEndpointHarness:
    """Raw Cypher execution/validation endpoints with mock Neo4j."""

    async def test_execute_read_query(self, harness_client: Any) -> None:
        """POST /api/v1/cypher/execute with MATCH count query returns results."""
        client, session, _app = harness_client
        _reset(session, [MockNeo4jResult([{"cnt": 1}])])

        resp = await client.post(
            "/api/v1/cypher/execute",
            json={"cypher": "MATCH (n:_Test) RETURN count(n) AS cnt"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "results" in body
        assert len(body["results"]) == 1
        assert body["results"][0]["cnt"] >= 1

    async def test_execute_create_query(self, harness_client: Any) -> None:
        """POST with CREATE (_Test) RETURN n → rowCount=1 and node returned."""
        client, session, _app = harness_client
        node = make_neo4j_node(
            element_id="4:test:999",
            labels=["_Test"],
            props={"name": "cypher_test_node"},
        )
        _reset(session, [MockNeo4jResult([{"n": node}])])

        resp = await client.post(
            "/api/v1/cypher/execute",
            json={"cypher": "CREATE (n:_Test {name: 'cypher_test_node'}) RETURN n"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["rowCount"] == 1
        assert len(body["results"]) == 1
        node_val = body["results"][0].get("n")
        assert node_val is not None
        if isinstance(node_val, dict) and "properties" in node_val:
            assert node_val["properties"].get("name") == "cypher_test_node"

    async def test_validate_valid_query(self, harness_client: Any) -> None:
        """POST /api/v1/cypher/validate with valid Cypher → valid=true.

        No session call needed — validation is pure logic (no Neo4j I/O).
        """
        client, session, _app = harness_client
        # No side_effects needed; validate endpoint does not call session.run()

        resp = await client.post(
            "/api/v1/cypher/validate",
            json={"cypher": "MATCH (n:Vessel) WHERE n.name = $name RETURN n"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["valid"] is True

    async def test_execute_dangerous_blocked(self, harness_client: Any) -> None:
        """POST Cypher containing DROP keyword → 403 Forbidden.

        No session call — the danger filter rejects before any DB access.
        """
        client, session, _app = harness_client
        # No side_effects needed; filter returns 403 before running query

        resp = await client.post(
            "/api/v1/cypher/execute",
            json={"cypher": "DROP INDEX my_index IF EXISTS"},
        )
        assert resp.status_code == 403, resp.text
