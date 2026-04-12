"""Shared mock Neo4j helpers for test harness.

Provides FakeNode, FakeRelationship, MockNeo4jSession and helper functions
for building mock records. These are extracted from test_api_crud.py so they
can be reused across integration and E2E harness tests.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fake Neo4j node / relationship types
# ---------------------------------------------------------------------------


class FakeNode:
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


def make_neo4j_node(
    element_id: str = "4:abc:1",
    labels: list[str] | None = None,
    props: dict[str, Any] | None = None,
) -> FakeNode:
    """Build a fake Neo4j Node object compatible with ``_extract_node``."""
    return FakeNode(
        element_id=element_id,
        labels=labels or ["Vessel"],
        props=props or {"name": "Test Vessel", "mmsi": "123456789"},
    )


class FakeRelationship:
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


def make_neo4j_relationship(
    element_id: str = "5:abc:1",
    rel_type: str = "DOCKED_AT",
    src_id: str = "4:abc:1",
    tgt_id: str = "4:abc:2",
    props: dict[str, Any] | None = None,
) -> FakeRelationship:
    """Build a fake Neo4j Relationship compatible with ``_extract_relationship``."""
    return FakeRelationship(
        element_id=element_id,
        rel_type=rel_type,
        src_id=src_id,
        tgt_id=tgt_id,
        props=props or {},
    )


# ---------------------------------------------------------------------------
# Async mock result / session types
# ---------------------------------------------------------------------------


class MockAsyncIterator:
    """Async iterator over a list of records."""

    def __init__(self, records: list[Any]) -> None:
        self._records = records
        self._index = 0

    def __aiter__(self) -> "MockAsyncIterator":
        return self

    async def __anext__(self) -> Any:
        if self._index >= len(self._records):
            raise StopAsyncIteration
        record = self._records[self._index]
        self._index += 1
        return record


class MockNeo4jResult:
    """Mock Neo4j query result supporting ``async for`` and ``.consume()``."""

    def __init__(self, records: list[Any]) -> None:
        self._records = records
        self._iter = MockAsyncIterator(records)

    def __aiter__(self) -> MockAsyncIterator:
        return MockAsyncIterator(self._records)

    async def single(self) -> Any | None:
        """Return first record or None — mirrors neo4j AsyncResult.single()."""
        return self._records[0] if self._records else None

    async def consume(self) -> MagicMock:
        summary = MagicMock()
        summary.plan = None
        return summary


class MockNeo4jSession:
    """Mock async Neo4j session."""

    def __init__(self, side_effects: list[Any] | None = None) -> None:
        """Initialise with a list of results to return for consecutive run() calls."""
        self._side_effects = side_effects or []
        self._call_index = 0

    async def run(self, cypher: str, params: dict[str, Any] | None = None, **kwargs: Any) -> MockNeo4jResult:
        if self._call_index < len(self._side_effects):
            result = self._side_effects[self._call_index]
        else:
            result = []
        self._call_index += 1
        if isinstance(result, MockNeo4jResult):
            return result
        return MockNeo4jResult(result)

    async def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Record builder helpers
# ---------------------------------------------------------------------------


def build_node_record(node: MagicMock) -> dict[str, Any]:
    """Build a plain dict record wrapping a node under key 'n'.

    ``_extract_node`` checks ``isinstance(record, dict)``, so the record must
    be a real dict.
    """
    return {"n": node}


def build_node_record_ab(
    node_a: MagicMock,
    rel: MagicMock,
    node_b: MagicMock,
) -> dict[str, Any]:
    """Build a plain dict record with keys 'a', 'r', 'b'."""
    return {"a": node_a, "r": rel, "b": node_b}


def build_rel_record(rel: MagicMock) -> dict[str, Any]:
    """Build a plain dict record wrapping a relationship under key 'r'."""
    return {"r": rel}


def count_record(total: int) -> dict[str, Any]:
    """Build a plain dict record with a 'total' field."""
    return {"total": total, "cnt": total}


# ---------------------------------------------------------------------------
# Test app factory
# ---------------------------------------------------------------------------


def make_test_app(session: MockNeo4jSession, config: Any) -> TestClient:
    """Create a FastAPI test client with the mock session injected."""
    from kg.api.app import create_app
    from kg.api.deps import get_async_neo4j_session

    with patch("kg.api.app.get_config", return_value=config), patch(
        "kg.api.app.set_config"
    ):
        app = create_app(config=config)

    async def _override_session():
        yield session

    app.dependency_overrides[get_async_neo4j_session] = _override_session
    return TestClient(app)
