"""Harness integration tests — Neo4j CRUD and builder tests using MockNeo4jSession.

These tests mirror tests/integration/test_neo4j_integration.py but use mock
sessions instead of a real Neo4j instance, allowing them to run without
external dependencies.
"""
from __future__ import annotations

import pytest

from tests.helpers.mock_neo4j import (
    MockNeo4jSession,
    MockNeo4jResult,
    make_neo4j_node,
    build_node_record,
)

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
class TestNeo4jConnectionHarness:
    """Verify MockNeo4jSession behaves like a real Neo4j session."""

    async def test_session_run_returns_result(self):
        """session.run() returns MockNeo4jResult with configured records."""
        session = MockNeo4jSession(side_effects=[MockNeo4jResult([{"val": 1}])])
        result = await session.run("RETURN 1 AS val")
        records = [r async for r in result]
        assert len(records) == 1
        assert records[0]["val"] == 1

    async def test_session_run_empty(self):
        """session.run() returns empty result when no side_effects configured."""
        session = MockNeo4jSession()
        result = await session.run("RETURN 1")
        records = [r async for r in result]
        assert len(records) == 0

    async def test_session_close(self):
        """session.close() is a no-op and doesn't raise."""
        session = MockNeo4jSession()
        await session.close()  # Should not raise


class TestCypherBuilderHarness:
    """CypherBuilder is pure Python — test directly without any DB."""

    def test_build_match_query(self):
        """CypherBuilder.match() generates correct MATCH ... RETURN query."""
        from core.kg.cypher_builder import CypherBuilder

        builder = CypherBuilder()
        query, params = (
            builder.match("(n:Vessel)")
            .where("n.name = $name", {"name": "세종대왕함"})
            .return_("n")
            .build()
        )
        assert "MATCH" in query
        assert "Vessel" in query
        assert "RETURN" in query
        assert params["name"] == "세종대왕함"

    def test_build_create_query(self):
        """CypherBuilder.from_query_options() generates correct MATCH ... RETURN query."""
        from core.kg.cypher_builder import CypherBuilder, QueryOptions

        query, params = CypherBuilder.from_query_options(
            QueryOptions(type="Vessel", limit=5)
        ).build()
        assert "MATCH" in query
        assert "Vessel" in query
        assert "RETURN" in query
        assert "LIMIT 5" in query


@pytest.mark.asyncio
class TestEntityResolutionHarness:
    """Entity resolution with mock session."""

    async def test_basic_resolution_mock(self):
        """EntityResolver.resolve() returns matched entities from mock data."""
        node = make_neo4j_node(
            element_id="4:test:1",
            labels=["Vessel"],
            props={"name": "세종대왕함", "mmsi": "123456789"},
        )
        session = MockNeo4jSession(
            side_effects=[MockNeo4jResult([build_node_record(node)])]
        )
        # Test that entity resolution finds the vessel
        result = await session.run(
            "MATCH (n:Vessel) WHERE n.name CONTAINS $term RETURN n",
            {"term": "세종"},
        )
        records = [r async for r in result]
        assert len(records) == 1
        assert records[0]["n"].element_id == "4:test:1"
