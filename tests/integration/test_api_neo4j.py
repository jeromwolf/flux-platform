"""FastAPI API endpoint integration tests against a real running Neo4j instance.

These tests exercise the full HTTP layer (routing, auth bypass in dev mode,
serialisation) using httpx.AsyncClient with ASGITransport.

Prerequisites
-------------
- Neo4j must be running and reachable.
- Set the environment variable ``NEO4J_TEST_URI`` to enable this test module.
  Example::

      NEO4J_TEST_URI=bolt://localhost:7687 \\
      NEO4J_TEST_USER=neo4j \\
      NEO4J_TEST_PASSWORD=fluxrag2026 \\
      PYTHONPATH=.:core:domains \\
      python -m pytest tests/integration/test_api_neo4j.py -m integration -v
"""

from __future__ import annotations

import os
import time
from typing import Any

import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport

# ---------------------------------------------------------------------------
# Module-level marks: skip entire module when NEO4J_TEST_URI is not set.
# All tests are integration tests and async.
# ---------------------------------------------------------------------------

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not os.environ.get("NEO4J_TEST_URI"),
        reason="NEO4J_TEST_URI not set — skip API integration tests",
    ),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NEO4J_URI = os.environ.get("NEO4J_TEST_URI", "bolt://localhost:7687")
_NEO4J_USER = os.environ.get("NEO4J_TEST_USER", "neo4j")
_NEO4J_PASSWORD = os.environ.get("NEO4J_TEST_PASSWORD", "fluxrag2026")


def _get_sync_driver():
    """Return a synchronous Neo4j driver using test credentials."""
    from neo4j import GraphDatabase

    return GraphDatabase.driver(_NEO4J_URI, auth=(_NEO4J_USER, _NEO4J_PASSWORD))


def _cleanup_test_nodes() -> None:
    """Delete all nodes/relationships carrying the _Test label synchronously."""
    driver = _get_sync_driver()
    try:
        with driver.session(database="neo4j") as session:
            session.run("MATCH (n:_Test) DETACH DELETE n")
    finally:
        driver.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client():
    """Create a FastAPI test client backed by a real Neo4j instance.

    Steps
    -----
    1. Instantiate AppConfig with real credentials and ``env="development"``
       so that API-key auth is bypassed.
    2. Register the config singleton via ``set_config()``.
    3. Build the FastAPI app via ``create_app()``.
    4. Yield an httpx.AsyncClient using ASGITransport (no real TCP port needed).
    5. Tear down: call ``reset()`` to clear the config/driver singletons.
    """
    from kg.config import AppConfig, Neo4jConfig, set_config, reset

    neo4j_cfg = Neo4jConfig(
        uri=_NEO4J_URI,
        user=_NEO4J_USER,
        password=_NEO4J_PASSWORD,
        database="neo4j",
    )
    config = AppConfig(env="development", neo4j=neo4j_cfg)
    set_config(config)

    from kg.api.app import create_app

    app = create_app(config)

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    reset()


@pytest.fixture(autouse=True)
def clean_test_nodes():
    """Remove _Test nodes before and after every test for isolation."""
    _cleanup_test_nodes()
    yield
    _cleanup_test_nodes()


# ---------------------------------------------------------------------------
# Utility coroutines shared across test classes
# ---------------------------------------------------------------------------


async def _create_test_vessel(ac: httpx.AsyncClient, name: str = "세종대왕함") -> dict[str, Any]:
    """Create a _Test:Vessel node and return the parsed JSON body."""
    resp = await ac.post(
        "/api/v1/nodes",
        json={"labels": ["_Test", "Vessel"], "properties": {"name": name}},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_test_port(ac: httpx.AsyncClient, name: str = "부산항") -> dict[str, Any]:
    """Create a _Test:Port node and return the parsed JSON body."""
    resp = await ac.post(
        "/api/v1/nodes",
        json={"labels": ["_Test", "Port"], "properties": {"name": name}},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_docked_at(
    ac: httpx.AsyncClient, vessel_id: str, port_id: str
) -> dict[str, Any]:
    """Create a DOCKED_AT relationship from vessel to port."""
    resp = await ac.post(
        "/api/v1/relationships",
        json={
            "sourceId": vessel_id,
            "targetId": port_id,
            "type": "DOCKED_AT",
            "properties": {},
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ===========================================================================
# TestHealthEndpoint
# ===========================================================================


class TestHealthEndpoint:
    """Verify the /api/v1/health endpoint against a live Neo4j."""

    async def test_health_returns_ok(self, client: httpx.AsyncClient) -> None:
        """GET /api/v1/health returns status='ok' and neo4j_connected=true."""
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "ok"
        assert body["neo4j_connected"] is True

    async def test_health_deep(self, client: httpx.AsyncClient) -> None:
        """GET /api/v1/health?deep=true returns a 'components' list."""
        resp = await client.get("/api/v1/health", params={"deep": "true"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "components" in body
        assert isinstance(body["components"], list)
        assert len(body["components"]) > 0
        # Neo4j component should be present and ok
        neo4j_component = next(
            (c for c in body["components"] if c["name"] == "neo4j"), None
        )
        assert neo4j_component is not None, "Expected 'neo4j' in components"
        assert neo4j_component["status"] == "ok"

    async def test_health_response_time(self, client: httpx.AsyncClient) -> None:
        """Health endpoint must respond within 2 seconds."""
        start = time.monotonic()
        resp = await client.get("/api/v1/health")
        elapsed = time.monotonic() - start
        assert resp.status_code == 200
        assert elapsed < 2.0, f"Health endpoint too slow: {elapsed:.3f}s"


# ===========================================================================
# TestNodesCRUD
# ===========================================================================


class TestNodesCRUD:
    """CRUD operations on the /api/v1/nodes endpoints against real Neo4j."""

    async def test_create_node(self, client: httpx.AsyncClient) -> None:
        """POST /api/v1/nodes creates a node and returns 201 with id/labels."""
        node = await _create_test_vessel(client)
        assert "id" in node
        assert "_Test" in node["labels"]
        assert "Vessel" in node["labels"]
        assert node["properties"].get("name") == "세종대왕함"

    async def test_get_node(self, client: httpx.AsyncClient) -> None:
        """Create a node then GET it by ID — returns 200 with correct data."""
        created = await _create_test_vessel(client, name="독도함")
        node_id = created["id"]

        resp = await client.get(f"/api/v1/nodes/{node_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["id"] == node_id
        assert body["properties"].get("name") == "독도함"

    async def test_update_node(self, client: httpx.AsyncClient) -> None:
        """Create then PUT with new properties — merged properties returned."""
        created = await _create_test_vessel(client, name="충무공함")
        node_id = created["id"]

        resp = await client.put(
            f"/api/v1/nodes/{node_id}",
            json={"properties": {"type": "destroyer", "active": True}},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # Original property preserved, new properties added
        assert body["properties"].get("name") == "충무공함"
        assert body["properties"].get("type") == "destroyer"
        assert body["properties"].get("active") is True

    async def test_delete_node(self, client: httpx.AsyncClient) -> None:
        """Create then DELETE — returns {"deleted": true}."""
        created = await _create_test_vessel(client, name="삭제함")
        node_id = created["id"]

        resp = await client.delete(f"/api/v1/nodes/{node_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["deleted"] is True

        # Confirm node is really gone
        get_resp = await client.get(f"/api/v1/nodes/{node_id}")
        assert get_resp.status_code == 404

    async def test_list_nodes(self, client: httpx.AsyncClient) -> None:
        """Create 3 _Test nodes, GET /api/v1/nodes?label=_Test returns >= 3."""
        for i in range(3):
            await _create_test_vessel(client, name=f"함정{i}")

        resp = await client.get("/api/v1/nodes", params={"label": "_Test"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] >= 3
        assert len(body["nodes"]) >= 3

    async def test_list_nodes_pagination(self, client: httpx.AsyncClient) -> None:
        """Create 5 nodes, request limit=2 → 2 nodes returned, total >= 5."""
        for i in range(5):
            await _create_test_vessel(client, name=f"페이지함{i}")

        resp = await client.get(
            "/api/v1/nodes", params={"label": "_Test", "limit": 2}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body["nodes"]) == 2
        assert body["total"] >= 5

    async def test_get_nonexistent_node(self, client: httpx.AsyncClient) -> None:
        """GET with a fake ID returns 404."""
        fake_id = "4:00000000-0000-0000-0000-000000000000:999999"
        resp = await client.get(f"/api/v1/nodes/{fake_id}")
        assert resp.status_code == 404, resp.text


# ===========================================================================
# TestRelationshipsCRUD
# ===========================================================================


class TestRelationshipsCRUD:
    """CRUD operations on the /api/v1/relationships endpoints."""

    async def test_create_relationship(self, client: httpx.AsyncClient) -> None:
        """Create 2 _Test nodes, POST DOCKED_AT relationship → 201."""
        vessel = await _create_test_vessel(client, name="관계함")
        port = await _create_test_port(client, name="인천항")

        rel_data = await _create_docked_at(client, vessel["id"], port["id"])
        rel = rel_data["relationship"]
        assert "id" in rel
        assert rel["type"] == "DOCKED_AT"
        assert rel["sourceId"] == vessel["id"]
        assert rel["targetId"] == port["id"]

    async def test_get_relationship(self, client: httpx.AsyncClient) -> None:
        """Create a relationship then GET it by ID → 200 with correct data."""
        vessel = await _create_test_vessel(client, name="조회함")
        port = await _create_test_port(client, name="광양항")
        created = await _create_docked_at(client, vessel["id"], port["id"])
        rel_id = created["relationship"]["id"]

        resp = await client.get(f"/api/v1/relationships/{rel_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["relationship"]["id"] == rel_id
        assert body["relationship"]["type"] == "DOCKED_AT"

    async def test_update_relationship(self, client: httpx.AsyncClient) -> None:
        """Create relationship, PUT with properties → merged properties returned."""
        vessel = await _create_test_vessel(client, name="수정함")
        port = await _create_test_port(client, name="울산항")
        created = await _create_docked_at(client, vessel["id"], port["id"])
        rel_id = created["relationship"]["id"]

        resp = await client.put(
            f"/api/v1/relationships/{rel_id}",
            json={"properties": {"berth": "A1", "since": "2026-01-01"}},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["properties"].get("berth") == "A1"
        assert body["properties"].get("since") == "2026-01-01"

    async def test_delete_relationship(self, client: httpx.AsyncClient) -> None:
        """Create relationship then DELETE → {"deleted": true}."""
        vessel = await _create_test_vessel(client, name="삭제관계함")
        port = await _create_test_port(client, name="여수항")
        created = await _create_docked_at(client, vessel["id"], port["id"])
        rel_id = created["relationship"]["id"]

        resp = await client.delete(f"/api/v1/relationships/{rel_id}")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["deleted"] is True

        # Confirm the relationship is truly gone
        get_resp = await client.get(f"/api/v1/relationships/{rel_id}")
        assert get_resp.status_code == 404

    async def test_list_relationships(self, client: httpx.AsyncClient) -> None:
        """Create 3 DOCKED_AT relationships, GET /api/v1/relationships → >= 3."""
        for i in range(3):
            vessel = await _create_test_vessel(client, name=f"목록함{i}")
            port = await _create_test_port(client, name=f"목록항{i}")
            await _create_docked_at(client, vessel["id"], port["id"])

        resp = await client.get("/api/v1/relationships", params={"type": "DOCKED_AT"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] >= 3


# ===========================================================================
# TestSchemaEndpoint
# ===========================================================================


class TestSchemaEndpoint:
    """Schema introspection endpoint against real Neo4j."""

    async def test_schema_returns_labels(self, client: httpx.AsyncClient) -> None:
        """After creating a _Test node, GET /api/v1/schema includes '_Test' label."""
        await _create_test_vessel(client, name="스키마함")

        resp = await client.get("/api/v1/schema")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "labels" in body
        label_names = [entry["label"] for entry in body["labels"]]
        assert "_Test" in label_names, f"'_Test' not found in labels: {label_names}"

    async def test_schema_returns_relationship_types(
        self, client: httpx.AsyncClient
    ) -> None:
        """After creating DOCKED_AT, schema includes that relationship type."""
        vessel = await _create_test_vessel(client, name="스키마관계함")
        port = await _create_test_port(client, name="스키마항")
        await _create_docked_at(client, vessel["id"], port["id"])

        resp = await client.get("/api/v1/schema")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "relationshipTypes" in body
        assert "DOCKED_AT" in body["relationshipTypes"], (
            f"DOCKED_AT not in {body['relationshipTypes']}"
        )


# ===========================================================================
# TestCypherEndpoint
# ===========================================================================


class TestCypherEndpoint:
    """Raw Cypher execution/validation endpoints against real Neo4j."""

    async def test_execute_read_query(self, client: httpx.AsyncClient) -> None:
        """POST /api/v1/cypher/execute with MATCH/_Test count query returns results."""
        # Seed at least one node so the count is deterministic
        await _create_test_vessel(client, name="사이퍼함")

        resp = await client.post(
            "/api/v1/cypher/execute",
            json={"cypher": "MATCH (n:_Test) RETURN count(n) AS cnt"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "results" in body
        assert len(body["results"]) == 1
        assert body["results"][0]["cnt"] >= 1

    async def test_execute_create_query(self, client: httpx.AsyncClient) -> None:
        """POST with CREATE (_Test) RETURN n → rowCount=1 and node returned."""
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
        # The node dict may be serialised as {"id": ..., "labels": [...], "properties": {...}}
        if isinstance(node_val, dict) and "properties" in node_val:
            assert node_val["properties"].get("name") == "cypher_test_node"

    async def test_validate_valid_query(self, client: httpx.AsyncClient) -> None:
        """POST /api/v1/cypher/validate with valid Cypher → valid=true."""
        resp = await client.post(
            "/api/v1/cypher/validate",
            json={"cypher": "MATCH (n:Vessel) WHERE n.name = $name RETURN n"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["valid"] is True

    async def test_execute_dangerous_blocked(self, client: httpx.AsyncClient) -> None:
        """POST Cypher containing DROP keyword → 403 Forbidden."""
        resp = await client.post(
            "/api/v1/cypher/execute",
            json={"cypher": "DROP INDEX my_index IF EXISTS"},
        )
        assert resp.status_code == 403, resp.text
