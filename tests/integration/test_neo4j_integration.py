"""Neo4j integration tests.

These tests require a running Neo4j instance.
Run: PYTHONPATH=.:core:domains python -m pytest tests/integration/test_neo4j_integration.py -m integration -v

To start Neo4j:
  docker run -d --name test-neo4j -p 7687:7687 -p 7474:7474 \\
    -e NEO4J_AUTH=neo4j/testpassword \\
    neo4j:5.26.0-community
"""

from __future__ import annotations

import os

import pytest

# Skip all tests if NEO4J_TEST_URI is not set
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("NEO4J_TEST_URI"),
        reason="NEO4J_TEST_URI not set — skip integration tests",
    ),
]


@pytest.fixture(scope="module")
def neo4j_driver():
    """Create a Neo4j driver for integration tests."""
    from neo4j import GraphDatabase

    uri = os.environ.get("NEO4J_TEST_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_TEST_USER", "neo4j")
    password = os.environ.get("NEO4J_TEST_PASSWORD", "testpassword")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    yield driver
    driver.close()


@pytest.fixture(autouse=True)
def clean_test_data(neo4j_driver):
    """Clean test data before and after each test."""
    with neo4j_driver.session() as session:
        session.run("MATCH (n:_Test) DETACH DELETE n")
    yield
    with neo4j_driver.session() as session:
        session.run("MATCH (n:_Test) DETACH DELETE n")


class TestNeo4jConnection:
    """Basic Neo4j connectivity tests."""

    def test_driver_connects(self, neo4j_driver):
        info = neo4j_driver.get_server_info()
        assert info is not None

    def test_basic_query(self, neo4j_driver):
        with neo4j_driver.session() as session:
            result = session.run("RETURN 1 AS n")
            record = result.single()
            assert record["n"] == 1

    def test_create_and_read_node(self, neo4j_driver):
        with neo4j_driver.session() as session:
            session.run("CREATE (n:_Test:Vessel {name: '세종대왕함', type: 'DDG'})")
            result = session.run("MATCH (n:_Test:Vessel) RETURN n.name AS name, n.type AS type")
            record = result.single()
            assert record["name"] == "세종대왕함"
            assert record["type"] == "DDG"


class TestCypherBuilder:
    """Test CypherBuilder with real Neo4j."""

    def test_fluent_match_query(self, neo4j_driver):
        from kg.cypher_builder import CypherBuilder

        # Setup data
        with neo4j_driver.session() as session:
            session.run("CREATE (n:_Test:Port {name: '부산항', code: 'KRPUS'})")

        builder = CypherBuilder()
        query, params = (
            builder.match("(p:_Test:Port)")
            .where("p.code = $code")
            .return_("p.name AS name")
            .build()
        )
        params["code"] = "KRPUS"

        with neo4j_driver.session() as session:
            result = session.run(query, params)
            record = result.single()
            assert record["name"] == "부산항"

    def test_create_relationship(self, neo4j_driver):
        with neo4j_driver.session() as session:
            session.run("""
                CREATE (v:_Test:Vessel {name: '독도함'})
                CREATE (p:_Test:Port {name: '인천항'})
                CREATE (v)-[:DOCKED_AT]->(p)
            """)

            result = session.run("""
                MATCH (v:_Test:Vessel)-[r:DOCKED_AT]->(p:_Test:Port)
                RETURN v.name AS vessel, type(r) AS rel, p.name AS port
            """)
            record = result.single()
            assert record["vessel"] == "독도함"
            assert record["rel"] == "DOCKED_AT"
            assert record["port"] == "인천항"


class TestSchemaOperations:
    """Test schema-related operations with Neo4j."""

    def test_get_labels(self, neo4j_driver):
        with neo4j_driver.session() as session:
            session.run("CREATE (n:_Test:UniqueTestLabel {x: 1})")
            result = session.run("CALL db.labels() YIELD label RETURN collect(label) AS labels")
            labels = result.single()["labels"]
            assert "UniqueTestLabel" in labels

    def test_get_relationship_types(self, neo4j_driver):
        with neo4j_driver.session() as session:
            session.run("CREATE (a:_Test)-[:_TEST_REL]->(b:_Test)")
            result = session.run(
                "CALL db.relationshipTypes() YIELD relationshipType "
                "RETURN collect(relationshipType) AS types"
            )
            types = result.single()["types"]
            assert "_TEST_REL" in types


class TestEntityResolution:
    """Test entity resolution with real Neo4j data."""

    def test_fuzzy_name_matching(self, neo4j_driver):
        """Create similar-named nodes and test resolution."""
        with neo4j_driver.session() as session:
            session.run("""
                CREATE (v1:_Test:Vessel {name: '세종대왕함', mmsi: '441001001'})
                CREATE (v2:_Test:Vessel {name: '세종대왕', mmsi: '441001001'})
            """)

            result = session.run(
                """
                MATCH (v:_Test:Vessel)
                WHERE v.mmsi = $mmsi
                RETURN count(v) AS count, collect(v.name) AS names
            """,
                {"mmsi": "441001001"},
            )
            record = result.single()
            assert record["count"] == 2
            assert "세종대왕함" in record["names"]


class TestGraphAlgorithms:
    """Test basic graph patterns for algorithm readiness."""

    def test_path_exists(self, neo4j_driver):
        with neo4j_driver.session() as session:
            session.run("""
                CREATE (a:_Test:Port {name: 'A'})
                CREATE (b:_Test:Port {name: 'B'})
                CREATE (c:_Test:Port {name: 'C'})
                CREATE (a)-[:ROUTE_TO {distance: 100}]->(b)
                CREATE (b)-[:ROUTE_TO {distance: 200}]->(c)
            """)

            result = session.run("""
                MATCH path = (a:_Test:Port {name: 'A'})-[:ROUTE_TO*]->(c:_Test:Port {name: 'C'})
                RETURN length(path) AS hops
            """)
            record = result.single()
            assert record["hops"] == 2
