"""Unit tests for Node CRUD, Relationship CRUD, and Cypher endpoints.

All tests are marked ``@pytest.mark.unit`` and work without a live Neo4j
instance.  The async Neo4j session dependency is overridden via
``app.dependency_overrides``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from kg.api.app import create_app
from kg.api.deps import get_async_neo4j_session
from kg.config import AppConfig, Neo4jConfig, reset


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class _FakeNode:
    """Minimal fake Neo4j Node that satisfies the checks in ``_extract_node``."""

    def __init__(
        self,
        element_id: str,
        labels: list[str],
        props: dict[str, Any],
    ) -> None:
        self.element_id = element_id
        self.labels = frozenset(labels)
        self._props = props

    # Allow dict(node) to work
    def keys(self) -> Any:
        return self._props.keys()

    def __iter__(self) -> Any:
        return iter(self._props.items())

    def __getitem__(self, key: str) -> Any:
        return self._props[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._props.get(key, default)


def _make_neo4j_node(
    element_id: str = "4:abc:1",
    labels: list[str] | None = None,
    props: dict[str, Any] | None = None,
) -> _FakeNode:
    """Build a fake Neo4j Node object compatible with ``_extract_node``."""
    return _FakeNode(
        element_id=element_id,
        labels=labels or ["Vessel"],
        props=props or {"name": "Test Vessel", "mmsi": "123456789"},
    )


class _FakeRelationship:
    """Minimal fake Neo4j Relationship for ``_extract_relationship``."""

    def __init__(
        self,
        element_id: str,
        rel_type: str,
        src_id: str,
        tgt_id: str,
        props: dict[str, Any],
    ) -> None:
        self.element_id = element_id
        self.type = rel_type
        src = MagicMock()
        src.element_id = src_id
        tgt = MagicMock()
        tgt.element_id = tgt_id
        self.start_node = src
        self.end_node = tgt
        self._props = props

    def keys(self) -> Any:
        return self._props.keys()

    def __iter__(self) -> Any:
        return iter(self._props.items())

    def __getitem__(self, key: str) -> Any:
        return self._props[key]


def _make_neo4j_relationship(
    element_id: str = "5:abc:1",
    rel_type: str = "DOCKED_AT",
    src_id: str = "4:abc:1",
    tgt_id: str = "4:abc:2",
    props: dict[str, Any] | None = None,
) -> _FakeRelationship:
    """Build a fake Neo4j Relationship compatible with ``_extract_relationship``."""
    return _FakeRelationship(
        element_id=element_id,
        rel_type=rel_type,
        src_id=src_id,
        tgt_id=tgt_id,
        props=props or {},
    )


class _MockAsyncIterator:
    """Async iterator over a list of records."""

    def __init__(self, records: list[Any]) -> None:
        self._records = records
        self._index = 0

    def __aiter__(self) -> "_MockAsyncIterator":
        return self

    async def __anext__(self) -> Any:
        if self._index >= len(self._records):
            raise StopAsyncIteration
        record = self._records[self._index]
        self._index += 1
        return record


class _MockNeo4jResult:
    """Mock Neo4j query result supporting ``async for`` and ``.consume()``."""

    def __init__(self, records: list[Any]) -> None:
        self._records = records
        self._iter = _MockAsyncIterator(records)

    def __aiter__(self) -> _MockAsyncIterator:
        return _MockAsyncIterator(self._records)

    async def consume(self) -> MagicMock:
        summary = MagicMock()
        summary.plan = None
        return summary


class _MockNeo4jSession:
    """Mock async Neo4j session."""

    def __init__(self, side_effects: list[Any] | None = None) -> None:
        """Initialise with a list of results to return for consecutive run() calls."""
        self._side_effects = side_effects or []
        self._call_index = 0

    async def run(self, cypher: str, params: dict[str, Any] | None = None) -> _MockNeo4jResult:
        if self._call_index < len(self._side_effects):
            result = self._side_effects[self._call_index]
        else:
            result = []
        self._call_index += 1
        if isinstance(result, _MockNeo4jResult):
            return result
        return _MockNeo4jResult(result)

    async def close(self) -> None:
        pass


def _build_node_record(node: MagicMock) -> dict[str, Any]:
    """Build a plain dict record wrapping a node under key 'n'.

    ``_extract_node`` checks ``isinstance(record, dict)``, so the record must
    be a real dict.
    """
    return {"n": node}


def _build_node_record_ab(
    node_a: MagicMock,
    rel: MagicMock,
    node_b: MagicMock,
) -> dict[str, Any]:
    """Build a plain dict record with keys 'a', 'r', 'b'."""
    return {"a": node_a, "r": rel, "b": node_b}


def _build_rel_record(rel: MagicMock) -> dict[str, Any]:
    """Build a plain dict record wrapping a relationship under key 'r'."""
    return {"r": rel}


def _count_record(total: int) -> dict[str, Any]:
    """Build a plain dict record with a 'total' field."""
    return {"total": total, "cnt": total}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_config():
    """Reset config singleton before and after each test."""
    reset()
    yield
    reset()


@pytest.fixture
def dev_config() -> AppConfig:
    """Development AppConfig (auth bypass)."""
    return AppConfig(env="development", neo4j=Neo4jConfig(uri="bolt://mock:7687"))


def _make_app(session: _MockNeo4jSession, config: AppConfig) -> TestClient:
    """Create a FastAPI test client with the mock session injected."""
    with patch("kg.api.app.get_config", return_value=config), patch(
        "kg.api.app.set_config"
    ):
        app = create_app(config=config)

    async def _override_session():
        yield session

    app.dependency_overrides[get_async_neo4j_session] = _override_session
    return TestClient(app)


# ===========================================================================
# Node CRUD tests
# ===========================================================================


@pytest.mark.unit
class TestNodeCRUD:
    """Node CRUD endpoint unit tests."""

    # TC-NC01: POST /nodes creates a node
    def test_create_node_returns_201(self, dev_config: AppConfig):
        """POST /nodes with valid body returns 201 and NodeResponse."""
        node = _make_neo4j_node()
        record = _build_node_record(node)
        session = _MockNeo4jSession(side_effects=[_MockNeo4jResult([record])])
        client = _make_app(session, dev_config)

        resp = client.post(
            "/api/v1/nodes",
            json={"labels": ["Vessel"], "properties": {"name": "Test Vessel"}},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert "labels" in data
        assert "Vessel" in data["labels"]

    # TC-NC02: GET /nodes/{id} returns node
    def test_get_node_by_id(self, dev_config: AppConfig):
        """GET /nodes/{id} returns 200 and NodeResponse for existing node."""
        node = _make_neo4j_node(element_id="4:abc:42")
        record = _build_node_record(node)
        session = _MockNeo4jSession(side_effects=[_MockNeo4jResult([record])])
        client = _make_app(session, dev_config)

        resp = client.get("/api/v1/nodes/4:abc:42")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "4:abc:42"

    # TC-NC02 (not-found): GET /nodes/{id} missing node returns 404
    def test_get_node_not_found(self, dev_config: AppConfig):
        """GET /nodes/{id} returns 404 when node does not exist."""
        session = _MockNeo4jSession(side_effects=[_MockNeo4jResult([])])
        client = _make_app(session, dev_config)

        resp = client.get("/api/v1/nodes/nonexistent-id")
        assert resp.status_code == 404

    # TC-NC03: PUT /nodes/{id} updates properties
    def test_update_node(self, dev_config: AppConfig):
        """PUT /nodes/{id} returns 200 with updated NodeResponse."""
        node = _make_neo4j_node(props={"name": "Updated Vessel"})
        record = _build_node_record(node)
        session = _MockNeo4jSession(side_effects=[_MockNeo4jResult([record])])
        client = _make_app(session, dev_config)

        resp = client.put(
            "/api/v1/nodes/4:abc:1",
            json={"properties": {"name": "Updated Vessel"}},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["properties"]["name"] == "Updated Vessel"

    # TC-NC03 (not-found): PUT /nodes/{id} missing node returns 404
    def test_update_node_not_found(self, dev_config: AppConfig):
        """PUT /nodes/{id} returns 404 when node does not exist."""
        session = _MockNeo4jSession(side_effects=[_MockNeo4jResult([])])
        client = _make_app(session, dev_config)

        resp = client.put(
            "/api/v1/nodes/nonexistent",
            json={"properties": {"name": "X"}},
        )
        assert resp.status_code == 404

    # TC-NC04: DELETE /nodes/{id} deletes node
    def test_delete_node(self, dev_config: AppConfig):
        """DELETE /nodes/{id} returns 200 with deleted=True."""
        count_record = _count_record(1)
        # First run: count check; second run: delete
        session = _MockNeo4jSession(
            side_effects=[
                _MockNeo4jResult([count_record]),
                _MockNeo4jResult([]),
            ]
        )
        client = _make_app(session, dev_config)

        resp = client.delete("/api/v1/nodes/4:abc:1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] is True
        assert data["nodeId"] == "4:abc:1"

    # TC-NC04 (not-found): DELETE /nodes/{id} missing node returns 404
    def test_delete_node_not_found(self, dev_config: AppConfig):
        """DELETE /nodes/{id} returns 404 when node does not exist."""
        session = _MockNeo4jSession(side_effects=[_MockNeo4jResult([])])
        client = _make_app(session, dev_config)

        resp = client.delete("/api/v1/nodes/nonexistent")
        assert resp.status_code == 404

    # TC-NC05: GET /nodes returns paginated list
    def test_list_nodes(self, dev_config: AppConfig):
        """GET /nodes returns paginated NodeListResponse."""
        node = _make_neo4j_node()
        record = _build_node_record(node)
        count_record = _count_record(1)
        session = _MockNeo4jSession(
            side_effects=[
                _MockNeo4jResult([count_record]),
                _MockNeo4jResult([record]),
            ]
        )
        client = _make_app(session, dev_config)

        resp = client.get("/api/v1/nodes?limit=10&offset=0")

        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert data["limit"] == 10
        assert data["offset"] == 0

    # TC-NC06: POST /nodes with empty labels returns 422
    def test_create_node_empty_labels_returns_422(self, dev_config: AppConfig):
        """POST /nodes with empty labels list returns 422 Unprocessable Entity."""
        session = _MockNeo4jSession()
        client = _make_app(session, dev_config)

        resp = client.post(
            "/api/v1/nodes",
            json={"labels": [], "properties": {}},
        )

        assert resp.status_code == 422

    # Extra: POST /nodes with invalid label identifier returns 422
    def test_create_node_invalid_label_returns_422(self, dev_config: AppConfig):
        """POST /nodes with a non-identifier label returns 422."""
        session = _MockNeo4jSession()
        client = _make_app(session, dev_config)

        resp = client.post(
            "/api/v1/nodes",
            json={"labels": ["invalid-label!"], "properties": {}},
        )

        assert resp.status_code == 422


# ===========================================================================
# Relationship CRUD tests
# ===========================================================================


@pytest.mark.unit
class TestRelationshipCRUD:
    """Relationship CRUD endpoint unit tests."""

    # TC-RC01: POST /relationships creates relationship
    def test_create_relationship(self, dev_config: AppConfig):
        """POST /relationships with valid body returns 201."""
        src_node = _make_neo4j_node(element_id="4:abc:1")
        tgt_node = _make_neo4j_node(element_id="4:abc:2", labels=["Port"])
        rel = _make_neo4j_relationship()
        record = _build_node_record_ab(src_node, rel, tgt_node)
        session = _MockNeo4jSession(side_effects=[_MockNeo4jResult([record])])
        client = _make_app(session, dev_config)

        resp = client.post(
            "/api/v1/relationships",
            json={
                "sourceId": "4:abc:1",
                "targetId": "4:abc:2",
                "type": "DOCKED_AT",
                "properties": {"since": "2026-01-01"},
            },
        )

        assert resp.status_code == 201
        data = resp.json()
        assert "relationship" in data
        assert "sourceNode" in data
        assert "targetNode" in data
        assert data["relationship"]["type"] == "DOCKED_AT"

    # TC-RC01 (not-found): POST /relationships with missing nodes returns 404
    def test_create_relationship_nodes_not_found(self, dev_config: AppConfig):
        """POST /relationships returns 404 when source/target nodes don't exist."""
        session = _MockNeo4jSession(side_effects=[_MockNeo4jResult([])])
        client = _make_app(session, dev_config)

        resp = client.post(
            "/api/v1/relationships",
            json={
                "sourceId": "nonexistent-1",
                "targetId": "nonexistent-2",
                "type": "DOCKED_AT",
            },
        )
        assert resp.status_code == 404

    # TC-RC02: GET /relationships/{id} returns relationship
    def test_get_relationship(self, dev_config: AppConfig):
        """GET /relationships/{id} returns 200 with RelationshipDetailResponse."""
        src_node = _make_neo4j_node(element_id="4:abc:1")
        tgt_node = _make_neo4j_node(element_id="4:abc:2", labels=["Port"])
        rel = _make_neo4j_relationship(element_id="5:abc:99")
        record = _build_node_record_ab(src_node, rel, tgt_node)
        session = _MockNeo4jSession(side_effects=[_MockNeo4jResult([record])])
        client = _make_app(session, dev_config)

        resp = client.get("/api/v1/relationships/5:abc:99")

        assert resp.status_code == 200
        data = resp.json()
        assert data["relationship"]["id"] == "5:abc:99"

    # TC-RC02 (not-found): GET /relationships/{id} missing rel returns 404
    def test_get_relationship_not_found(self, dev_config: AppConfig):
        """GET /relationships/{id} returns 404 when relationship does not exist."""
        session = _MockNeo4jSession(side_effects=[_MockNeo4jResult([])])
        client = _make_app(session, dev_config)

        resp = client.get("/api/v1/relationships/nonexistent")
        assert resp.status_code == 404

    # TC-RC03: PUT /relationships/{id} updates properties
    def test_update_relationship(self, dev_config: AppConfig):
        """PUT /relationships/{id} returns 200 with updated EdgeResponse."""
        rel = _make_neo4j_relationship(props={"weight": 0.9})
        record = _build_rel_record(rel)
        session = _MockNeo4jSession(side_effects=[_MockNeo4jResult([record])])
        client = _make_app(session, dev_config)

        resp = client.put(
            "/api/v1/relationships/5:abc:1",
            json={"properties": {"weight": 0.9}},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "DOCKED_AT"

    # TC-RC03 (not-found): PUT /relationships/{id} missing rel returns 404
    def test_update_relationship_not_found(self, dev_config: AppConfig):
        """PUT /relationships/{id} returns 404 when relationship does not exist."""
        session = _MockNeo4jSession(side_effects=[_MockNeo4jResult([])])
        client = _make_app(session, dev_config)

        resp = client.put(
            "/api/v1/relationships/nonexistent",
            json={"properties": {"weight": 0.5}},
        )
        assert resp.status_code == 404

    # TC-RC04: DELETE /relationships/{id} deletes relationship
    def test_delete_relationship(self, dev_config: AppConfig):
        """DELETE /relationships/{id} returns 200 with deleted=True."""
        count_record = _count_record(1)
        session = _MockNeo4jSession(
            side_effects=[
                _MockNeo4jResult([count_record]),
                _MockNeo4jResult([]),
            ]
        )
        client = _make_app(session, dev_config)

        resp = client.delete("/api/v1/relationships/5:abc:1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] is True
        assert data["relationshipId"] == "5:abc:1"

    # TC-RC04 (not-found): DELETE /relationships/{id} missing rel returns 404
    def test_delete_relationship_not_found(self, dev_config: AppConfig):
        """DELETE /relationships/{id} returns 404 when relationship does not exist."""
        session = _MockNeo4jSession(side_effects=[_MockNeo4jResult([])])
        client = _make_app(session, dev_config)

        resp = client.delete("/api/v1/relationships/nonexistent")
        assert resp.status_code == 404

    # TC-RC05: POST /relationships with invalid type pattern returns 422
    def test_create_relationship_invalid_type_returns_422(self, dev_config: AppConfig):
        """POST /relationships with lowercase type returns 422."""
        session = _MockNeo4jSession()
        client = _make_app(session, dev_config)

        resp = client.post(
            "/api/v1/relationships",
            json={
                "sourceId": "4:abc:1",
                "targetId": "4:abc:2",
                "type": "docked_at",  # invalid: must be SCREAMING_SNAKE_CASE
            },
        )

        assert resp.status_code == 422

    def test_create_relationship_type_with_spaces_returns_422(self, dev_config: AppConfig):
        """POST /relationships with spaces in type returns 422."""
        session = _MockNeo4jSession()
        client = _make_app(session, dev_config)

        resp = client.post(
            "/api/v1/relationships",
            json={
                "sourceId": "4:abc:1",
                "targetId": "4:abc:2",
                "type": "DOCKED AT",
            },
        )
        assert resp.status_code == 422

    def test_list_relationships(self, dev_config: AppConfig):
        """GET /relationships returns paginated RelationshipListResponse."""
        rel = _make_neo4j_relationship()
        rel_record = _build_rel_record(rel)
        count_record = _count_record(1)
        session = _MockNeo4jSession(
            side_effects=[
                _MockNeo4jResult([count_record]),
                _MockNeo4jResult([rel_record]),
            ]
        )
        client = _make_app(session, dev_config)

        resp = client.get("/api/v1/relationships?limit=10")

        assert resp.status_code == 200
        data = resp.json()
        assert "relationships" in data
        assert "total" in data
        assert data["limit"] == 10


# ===========================================================================
# Cypher endpoint tests
# ===========================================================================


@pytest.mark.unit
class TestCypherEndpoints:
    """Cypher execution, validation, and explain endpoint unit tests."""

    # TC-CY01: POST /cypher/validate with valid Cypher returns valid=true
    def test_validate_valid_cypher(self, dev_config: AppConfig):
        """POST /cypher/validate with a valid MATCH/RETURN query returns valid=true."""
        session = _MockNeo4jSession()
        client = _make_app(session, dev_config)

        resp = client.post(
            "/api/v1/cypher/validate",
            json={"cypher": "MATCH (n:Vessel) RETURN n LIMIT 10"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["errors"] == []

    # TC-CY02: POST /cypher/validate detects write queries
    def test_validate_detects_write_query(self, dev_config: AppConfig):
        """POST /cypher/validate sets queryType='write' for CREATE queries."""
        session = _MockNeo4jSession()
        client = _make_app(session, dev_config)

        resp = client.post(
            "/api/v1/cypher/validate",
            json={"cypher": "CREATE (n:Vessel {name: 'Test'}) RETURN n"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["queryType"] == "write"

    def test_validate_detects_merge_as_write(self, dev_config: AppConfig):
        """POST /cypher/validate sets queryType='write' for MERGE queries."""
        session = _MockNeo4jSession()
        client = _make_app(session, dev_config)

        resp = client.post(
            "/api/v1/cypher/validate",
            json={
                "cypher": "MERGE (n:Vessel {mmsi: '123'}) ON CREATE SET n.name = 'New' RETURN n"
            },
        )

        assert resp.status_code == 200
        assert resp.json()["queryType"] == "write"

    def test_validate_read_query_type(self, dev_config: AppConfig):
        """POST /cypher/validate sets queryType='read' for MATCH-only queries."""
        session = _MockNeo4jSession()
        client = _make_app(session, dev_config)

        resp = client.post(
            "/api/v1/cypher/validate",
            json={"cypher": "MATCH (n) RETURN n"},
        )

        assert resp.status_code == 200
        assert resp.json()["queryType"] == "read"

    def test_validate_empty_cypher_returns_invalid(self, dev_config: AppConfig):
        """POST /cypher/validate with empty cypher returns valid=false."""
        session = _MockNeo4jSession()
        client = _make_app(session, dev_config)

        resp = client.post(
            "/api/v1/cypher/validate",
            json={"cypher": "   "},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0

    # TC-CY03: POST /cypher/execute with dangerous pattern returns 403
    def test_execute_drop_returns_403(self, dev_config: AppConfig):
        """POST /cypher/execute with DROP statement returns 403 Forbidden."""
        session = _MockNeo4jSession()
        client = _make_app(session, dev_config)

        resp = client.post(
            "/api/v1/cypher/execute",
            json={"cypher": "DROP INDEX vessel_name"},
        )

        assert resp.status_code == 403

    def test_execute_delete_without_where_returns_403(self, dev_config: AppConfig):
        """POST /cypher/execute with DELETE (no WHERE) returns 403 Forbidden."""
        session = _MockNeo4jSession()
        client = _make_app(session, dev_config)

        resp = client.post(
            "/api/v1/cypher/execute",
            json={"cypher": "MATCH (n) DETACH DELETE n"},
        )

        assert resp.status_code == 403

    def test_execute_safe_query_returns_200(self, dev_config: AppConfig):
        """POST /cypher/execute with a safe MATCH query returns 200."""
        row_record: dict[str, Any] = {}
        session = _MockNeo4jSession(side_effects=[_MockNeo4jResult([row_record])])
        client = _make_app(session, dev_config)

        resp = client.post(
            "/api/v1/cypher/execute",
            json={"cypher": "MATCH (n:Vessel) RETURN n.name AS name LIMIT 5"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "columns" in data
        assert "rowCount" in data
        assert "executionTimeMs" in data
        assert data["rowCount"] == 1

    def test_execute_returns_execution_time(self, dev_config: AppConfig):
        """POST /cypher/execute response includes non-negative executionTimeMs."""
        session = _MockNeo4jSession(side_effects=[_MockNeo4jResult([])])
        client = _make_app(session, dev_config)

        resp = client.post(
            "/api/v1/cypher/execute",
            json={"cypher": "MATCH (n:Vessel) RETURN n LIMIT 1"},
        )

        assert resp.status_code == 200
        assert resp.json()["executionTimeMs"] >= 0.0

    def test_execute_apoc_schema_returns_403(self, dev_config: AppConfig):
        """POST /cypher/execute with apoc.schema call returns 403."""
        session = _MockNeo4jSession()
        client = _make_app(session, dev_config)

        resp = client.post(
            "/api/v1/cypher/execute",
            json={"cypher": "CALL apoc.schema.assert({}, {})"},
        )

        assert resp.status_code == 403

    # TC-CY04: POST /cypher/explain returns plan structure
    def test_explain_returns_plan_structure(self, dev_config: AppConfig):
        """POST /cypher/explain returns 200 with plan dict and estimatedRows."""
        session = _MockNeo4jSession(side_effects=[_MockNeo4jResult([])])
        client = _make_app(session, dev_config)

        resp = client.post(
            "/api/v1/cypher/explain",
            json={"cypher": "MATCH (n:Vessel) RETURN n LIMIT 10"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "plan" in data
        assert "estimatedRows" in data
        assert isinstance(data["plan"], dict)
        assert isinstance(data["estimatedRows"], int)

    def test_explain_dangerous_query_returns_403(self, dev_config: AppConfig):
        """POST /cypher/explain with DROP returns 403 even without execution."""
        session = _MockNeo4jSession()
        client = _make_app(session, dev_config)

        resp = client.post(
            "/api/v1/cypher/explain",
            json={"cypher": "DROP CONSTRAINT vessel_mmsi"},
        )

        assert resp.status_code == 403
