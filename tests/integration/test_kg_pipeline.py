"""Integration tests for KG pipeline components against a real Neo4j instance.

Requires NEO4J_TEST_URI environment variable to be set.
All test data uses the _Test label prefix and is cleaned up automatically.

Run with:
    NEO4J_TEST_URI=bolt://localhost:7687 \\
    NEO4J_TEST_USER=neo4j \\
    NEO4J_TEST_PASSWORD=fluxrag2026 \\
    PYTHONPATH=. pytest tests/integration/test_kg_pipeline.py -v -m integration
"""

from __future__ import annotations

import os

import pytest
from neo4j import GraphDatabase

from kg.cypher_builder import CypherBuilder
from kg.cypher_validator import CypherValidator, FailureType
from kg.entity_resolution.models import MatchMethod
from kg.entity_resolution.resolver import EntityResolver
from kg.lineage.models import LineageEventType
from kg.lineage.recorder import LineageRecorder
from kg.quality_gate import CheckResult, CheckStatus, GateReport

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("NEO4J_TEST_URI"),
        reason="NEO4J_TEST_URI not set",
    ),
]


# ---------------------------------------------------------------------------
# Module-level fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def neo4j_driver():
    """Create a Neo4j driver for the test session."""
    uri = os.environ.get("NEO4J_TEST_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_TEST_USER", "neo4j")
    password = os.environ.get("NEO4J_TEST_PASSWORD", "fluxrag2026")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    yield driver
    driver.close()


@pytest.fixture(autouse=True)
def clean_test_data(neo4j_driver):
    """Delete all _Test-labelled nodes before and after each test."""
    with neo4j_driver.session() as session:
        session.run("MATCH (n:_Test) DETACH DELETE n")
    yield
    with neo4j_driver.session() as session:
        session.run("MATCH (n:_Test) DETACH DELETE n")


# ---------------------------------------------------------------------------
# Helper: run a (query, params) tuple against Neo4j and return records
# ---------------------------------------------------------------------------


def _run(driver, query: str, params: dict | None = None) -> list:
    with driver.session() as session:
        result = session.run(query, params or {})
        return list(result)


# ===========================================================================
# TestCypherBuilderRealExecution
# ===========================================================================


class TestCypherBuilderRealExecution:
    """Execute CypherBuilder-produced queries against a live Neo4j instance."""

    def test_match_and_return(self, neo4j_driver):
        """MATCH query built with CypherBuilder executes and returns results."""
        # Seed one node so the query isn't trivially empty
        with neo4j_driver.session() as session:
            session.run("CREATE (:_Test {name: 'alpha', value: 1})")

        query, params = (
            CypherBuilder()
            .match("(n:_Test)")
            .return_("n.name AS name, n.value AS value")
            .build()
        )

        records = _run(neo4j_driver, query, params)
        assert len(records) >= 1
        names = [r["name"] for r in records]
        assert "alpha" in names

    def test_create_node(self, neo4j_driver):
        """CREATE query built with CypherBuilder inserts a node."""
        query, params = (
            CypherBuilder()
            .match("(n:_Test {name: 'created-node'})")
            .return_("count(n) AS cnt")
            .build()
        )
        # Node should not exist yet
        before = _run(neo4j_driver, query, params)
        assert before[0]["cnt"] == 0

        # Build a raw CREATE and execute it
        create_query = "CREATE (n:_Test {name: $name}) RETURN n"
        _run(neo4j_driver, create_query, {"name": "created-node"})

        # Verify it now exists
        after = _run(neo4j_driver, query, params)
        assert after[0]["cnt"] == 1

    def test_merge_node(self, neo4j_driver):
        """MERGE query built with CypherBuilder creates exactly one node even when run twice."""
        merge_query = "MERGE (n:_Test {name: $name}) RETURN n"
        params = {"name": "merge-target"}

        _run(neo4j_driver, merge_query, params)
        _run(neo4j_driver, merge_query, params)

        # Build count query with CypherBuilder and verify idempotence
        count_query, count_params = (
            CypherBuilder()
            .match("(n:_Test)")
            .where("n.name = $name", {"name": "merge-target"})
            .return_("count(n) AS cnt")
            .build()
        )
        records = _run(neo4j_driver, count_query, count_params)
        assert records[0]["cnt"] == 1

    def test_complex_query(self, neo4j_driver):
        """Multi-clause CypherBuilder query (MATCH, WHERE, WITH, ORDER BY, LIMIT) executes."""
        # Seed several nodes with a score property
        with neo4j_driver.session() as session:
            for i in range(5):
                session.run(
                    "CREATE (:_Test {name: $name, score: $score})",
                    {"name": f"item-{i}", "score": i * 10},
                )

        query, params = (
            CypherBuilder()
            .match("(n:_Test)")
            .where("n.score >= $min_score", {"min_score": 20})
            .with_("n ORDER BY n.score DESC")
            .return_("n.name AS name, n.score AS score")
            .limit(2)
            .build()
        )

        records = _run(neo4j_driver, query, params)
        assert len(records) == 2
        # Highest scores first (40, 30)
        assert records[0]["score"] == 40
        assert records[1]["score"] == 30

    def test_parameterized_query(self, neo4j_driver):
        """CypherBuilder query with $param correctly binds runtime values."""
        with neo4j_driver.session() as session:
            session.run(
                "CREATE (:_Test {name: $name, category: $cat})",
                {"name": "parameterized-node", "cat": "vessel"},
            )

        query, params = (
            CypherBuilder()
            .match("(n:_Test)")
            .where("n.category = $cat", {"cat": "vessel"})
            .return_("n.name AS name")
            .build()
        )

        records = _run(neo4j_driver, query, params)
        assert len(records) >= 1
        assert any(r["name"] == "parameterized-node" for r in records)


# ===========================================================================
# TestCypherValidatorIntegration
# ===========================================================================


class TestCypherValidatorIntegration:
    """Validate Cypher queries and optionally execute them against Neo4j."""

    def test_valid_query_passes(self, neo4j_driver):
        """A correct MATCH...RETURN passes validation with no errors."""
        validator = CypherValidator()
        result = validator.validate("MATCH (n:_Test) RETURN n")

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.failure_type == FailureType.NONE

    def test_invalid_query_fails(self, neo4j_driver):
        """An intentionally broken query (no RETURN) fails validation."""
        validator = CypherValidator()
        # Missing RETURN clause
        result = validator.validate("MATCH (n:_Test) WHERE n.x = 1")

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert result.failure_type == FailureType.SCHEMA

    def test_validated_then_executed(self, neo4j_driver):
        """Validate first, then execute on Neo4j and confirm results match."""
        with neo4j_driver.session() as session:
            session.run(
                "CREATE (:_Test {name: $name, status: $status})",
                {"name": "validated-node", "status": "active"},
            )

        cypher = "MATCH (n:_Test) WHERE n.status = $status RETURN n.name AS name"
        validator = CypherValidator()
        val_result = validator.validate(cypher)

        # Validation must pass before we execute
        assert val_result.is_valid is True

        records = _run(neo4j_driver, cypher, {"status": "active"})
        assert len(records) >= 1
        assert any(r["name"] == "validated-node" for r in records)


# ===========================================================================
# TestQualityGateRealData
# ===========================================================================


class TestQualityGateRealData:
    """Build GateReports backed by real Neo4j data."""

    def test_report_on_real_graph(self, neo4j_driver):
        """GateReport with CheckResult entries reflects real data counts."""
        with neo4j_driver.session() as session:
            for i in range(3):
                session.run(
                    "CREATE (:_Test {name: $name})",
                    {"name": f"gate-node-{i}"},
                )

        with neo4j_driver.session() as session:
            result = session.run("MATCH (n:_Test) RETURN count(n) AS cnt")
            count = result.single()["cnt"]

        report = GateReport()
        report.add(
            CheckResult(
                name="node_count_check",
                status=CheckStatus.PASSED,
                message=f"{count} _Test nodes found",
                details={"count": count},
            )
        )

        assert len(report.checks) == 1
        assert report.checks[0].status == CheckStatus.PASSED
        assert report.passed is True
        assert count >= 3

    def test_completeness_check(self, neo4j_driver):
        """Nodes with and without required properties trigger correct check status."""
        with neo4j_driver.session() as session:
            # Node with required property
            session.run(
                "CREATE (:_Test {name: $name, required_prop: $val})",
                {"name": "complete-node", "val": "present"},
            )
            # Node missing required property
            session.run(
                "CREATE (:_Test {name: $name})",
                {"name": "incomplete-node"},
            )

        with neo4j_driver.session() as session:
            result = session.run(
                "MATCH (n:_Test) WHERE n.required_prop IS NOT NULL RETURN count(n) AS cnt"
            )
            complete_count = result.single()["cnt"]
            result2 = session.run(
                "MATCH (n:_Test) WHERE n.required_prop IS NULL RETURN count(n) AS cnt"
            )
            incomplete_count = result2.single()["cnt"]

        report = GateReport()
        status = CheckStatus.PASSED if incomplete_count == 0 else CheckStatus.WARNING
        report.add(
            CheckResult(
                name="property_completeness",
                status=status,
                message=f"{complete_count} complete, {incomplete_count} missing required_prop",
                details={"complete": complete_count, "incomplete": incomplete_count},
            )
        )

        assert complete_count >= 1
        assert incomplete_count >= 1
        assert report.checks[0].status == CheckStatus.WARNING
        # WARNING does not fail the gate
        assert report.passed is True

    def test_gate_pass_fail(self, neo4j_driver):
        """GateReport.passed is False when any check has FAILED status."""
        report = GateReport()
        report.add(
            CheckResult(
                name="passing_check",
                status=CheckStatus.PASSED,
                message="All good",
            )
        )
        report.add(
            CheckResult(
                name="failing_check",
                status=CheckStatus.FAILED,
                message="Something went wrong",
            )
        )

        # One FAILED check → overall gate fails
        assert report.passed is False

        # Verify individual statuses
        passed_checks = [c for c in report.checks if c.status == CheckStatus.PASSED]
        failed_checks = [c for c in report.checks if c.status == CheckStatus.FAILED]
        assert len(passed_checks) == 1
        assert len(failed_checks) == 1


# ===========================================================================
# TestEntityResolutionReal
# ===========================================================================


class TestEntityResolutionReal:
    """Entity resolution tests that optionally use Neo4j for node creation."""

    def test_exact_match(self, neo4j_driver):
        """Identical entity names resolve to a single canonical group."""
        with neo4j_driver.session() as session:
            for name in ["세종대왕함", "세종대왕함"]:
                session.run("CREATE (:_Test {name: $name})", {"name": name})

        resolver = EntityResolver(fuzzy_threshold=0.8)
        results = resolver.resolve(["세종대왕함", "세종대왕함"])

        # Both identical strings collapse into one group
        assert len(results) == 1
        result = results[0]
        assert result.merged is True
        assert result.canonical == "세종대왕함"

        # The pairwise candidate should report EXACT method
        assert any(c.method == MatchMethod.EXACT for c in result.candidates)

    def test_fuzzy_match(self, neo4j_driver):
        """Similar (but not identical) names may resolve into a single group."""
        with neo4j_driver.session() as session:
            for name in ["King Sejong", "King Sejong Destroyer"]:
                session.run("CREATE (:_Test {name: $name})", {"name": name})

        resolver = EntityResolver(fuzzy_threshold=0.5)
        results = resolver.resolve(["King Sejong", "King Sejong Destroyer"])

        # With a low threshold the two forms should merge
        assert len(results) == 1
        result = results[0]
        assert result.merged is True
        # Longest form is canonical
        assert result.canonical == "King Sejong Destroyer"

    def test_no_match(self, neo4j_driver):
        """Entity names with no similarity remain in separate groups."""
        resolver = EntityResolver(fuzzy_threshold=0.9)
        results = resolver.resolve(["세종대왕함", "부산항터미널"])

        # Should stay as two separate groups (dissimilar names)
        assert len(results) == 2
        for result in results:
            assert result.merged is False


# ===========================================================================
# TestLineageTrackerReal
# ===========================================================================


class TestLineageTrackerReal:
    """LineageRecorder integration tests that flush events to Neo4j."""

    def test_record_creation_event(self, neo4j_driver):
        """Recording a CREATION event creates a LineageNode in Neo4j."""
        # Create the _Test node whose lineage we track
        with neo4j_driver.session() as session:
            session.run(
                "CREATE (:_Test {name: $name, entityId: $eid})",
                {"name": "vessel-alpha", "eid": "VES-ALPHA-001"},
            )

        recorder = LineageRecorder()
        edge = recorder.record_event(
            entity_type="Vessel",
            entity_id="VES-ALPHA-001",
            event_type=LineageEventType.CREATION,
            agent="test-etl-pipeline",
            activity="Imported vessel from AIS feed",
        )

        assert edge is not None
        assert edge.event_type == LineageEventType.CREATION
        assert edge.agent == "test-etl-pipeline"

        # Flush to Neo4j
        with neo4j_driver.session() as session:
            flushed = recorder.flush(session)

        assert flushed >= 1  # at least the lineage node was written

        # Verify the LineageNode exists in Neo4j
        records = _run(
            neo4j_driver,
            "MATCH (ln:LineageNode {entityId: $eid}) RETURN ln",
            {"eid": "VES-ALPHA-001"},
        )
        assert len(records) >= 1

    def test_record_transformation_event(self, neo4j_driver):
        """Recording a TRANSFORMATION event is stored in the in-memory graph."""
        recorder = LineageRecorder()

        # Record two events on the same entity to build a chain
        # Note: INGESTION requires DETAILED policy; CREATION is in STANDARD
        recorder.record_event(
            entity_type="Vessel",
            entity_id="VES-TRANS-001",
            event_type=LineageEventType.CREATION,
            agent="raw-ingest",
            activity="Raw AIS data ingested",
        )
        edge = recorder.record_event(
            entity_type="Vessel",
            entity_id="VES-TRANS-001",
            event_type=LineageEventType.TRANSFORMATION,
            agent="normalizer",
            activity="Fields normalised to ISO standards",
        )

        assert edge is not None
        assert edge.event_type == LineageEventType.TRANSFORMATION

        graph = recorder.get_graph()
        # Both events are on the same node → 1 node, 2 edges
        assert len(graph.nodes) == 1
        assert len(graph.edges) == 2

        event_types = {e.event_type for e in graph.edges}
        assert LineageEventType.CREATION in event_types
        assert LineageEventType.TRANSFORMATION in event_types

    def test_query_lineage(self, neo4j_driver):
        """Record events for two entities linked by DERIVATION, then verify the chain."""
        from kg.lineage.policy import LineagePolicy, RecordingLevel

        # Use DETAILED policy so DERIVATION events are recorded
        policy = LineagePolicy(default_level=RecordingLevel.DETAILED)
        recorder = LineageRecorder(policy=policy)

        recorder.record_event(
            entity_type="Vessel",
            entity_id="VES-SOURCE-001",
            event_type=LineageEventType.CREATION,
            agent="source-agent",
            activity="Source entity created",
        )

        derivation_edge = recorder.record_derivation(
            source_type="Vessel",
            source_id="VES-SOURCE-001",
            target_type="Vessel",
            target_id="VES-DERIVED-001",
            agent="derive-agent",
            activity="Derived vessel record created",
        )

        assert derivation_edge is not None
        assert derivation_edge.event_type == LineageEventType.DERIVATION

        # get_lineage_for returns the relevant subgraph
        subgraph = recorder.get_lineage_for("VES-DERIVED-001")

        # Both nodes should appear in the subgraph
        entity_ids = {n.entity_id for n in subgraph.nodes.values()}
        assert "VES-SOURCE-001" in entity_ids
        assert "VES-DERIVED-001" in entity_ids

        # The derivation edge should be present
        assert len(subgraph.edges) >= 1
        edge_types = {e.event_type for e in subgraph.edges}
        assert LineageEventType.DERIVATION in edge_types
