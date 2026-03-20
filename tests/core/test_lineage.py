"""Comprehensive unit tests for the kg.lineage package.

Tests cover all four sub-modules: models, policy, recorder, and queries.
No Neo4j connection required - all tests are pure Python unit tests.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from kg.lineage import queries
from kg.lineage.models import (
    DataSnapshot,
    LineageEdge,
    LineageEventType,
    LineageGraph,
    LineageNode,
    ProvenanceRole,
)
from kg.lineage.policy import (
    LineagePolicy,
    RecordingLevel,
)
from kg.lineage.recorder import LineageRecorder

# =============================================================================
# Helper fixtures
# =============================================================================


@pytest.fixture()
def sample_node() -> LineageNode:
    """Create a sample LineageNode for testing."""
    return LineageNode(
        node_id="node-001",
        entity_type="Vessel",
        entity_id="VES-001",
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        metadata={"source": "AIS"},
    )


@pytest.fixture()
def sample_edge() -> LineageEdge:
    """Create a sample LineageEdge for testing."""
    return LineageEdge(
        edge_id="edge-001",
        source_id="node-001",
        target_id="node-002",
        event_type=LineageEventType.DERIVATION,
        timestamp=datetime(2025, 1, 2, tzinfo=timezone.utc),
        agent="ETL-Pipeline-1",
        activity="Derived vessel statistics",
        metadata={"version": "1.0"},
    )


@pytest.fixture()
def chain_graph() -> LineageGraph:
    """Create a lineage graph with a chain: A -> B -> C and B -> D.

    Edges go from source to target, representing derivation:
    A is ancestor of B, B is ancestor of C and D.
    """
    graph = LineageGraph()
    nodes = {
        "A": LineageNode(node_id="A", entity_type="Dataset", entity_id="DS-A"),
        "B": LineageNode(node_id="B", entity_type="Dataset", entity_id="DS-B"),
        "C": LineageNode(node_id="C", entity_type="Dataset", entity_id="DS-C"),
        "D": LineageNode(node_id="D", entity_type="Report", entity_id="RPT-D"),
    }
    for node in nodes.values():
        graph.add_node(node)

    graph.add_edge(LineageEdge(
        edge_id="e1", source_id="A", target_id="B",
        event_type=LineageEventType.DERIVATION,
    ))
    graph.add_edge(LineageEdge(
        edge_id="e2", source_id="B", target_id="C",
        event_type=LineageEventType.TRANSFORMATION,
    ))
    graph.add_edge(LineageEdge(
        edge_id="e3", source_id="B", target_id="D",
        event_type=LineageEventType.DERIVATION,
    ))
    return graph


# =============================================================================
# Models - LineageEventType
# =============================================================================


@pytest.mark.unit
class TestLineageEventType:
    """Tests for LineageEventType enum."""

    def test_all_event_types_present(self):
        """All 8 event types are defined."""
        expected = {
            "CREATION", "TRANSFORMATION", "DERIVATION", "INGESTION",
            "EXPORT", "DELETION", "MERGE", "SPLIT",
        }
        assert {e.value for e in LineageEventType} == expected

    def test_event_type_is_str_enum(self):
        """LineageEventType values are strings usable directly."""
        assert LineageEventType.CREATION == "CREATION"
        assert isinstance(LineageEventType.TRANSFORMATION, str)


# =============================================================================
# Models - ProvenanceRole
# =============================================================================


@pytest.mark.unit
class TestProvenanceRole:
    """Tests for ProvenanceRole enum."""

    def test_all_roles_present(self):
        """All 3 PROV-O roles are defined."""
        assert {r.value for r in ProvenanceRole} == {"AGENT", "ENTITY", "ACTIVITY"}


# =============================================================================
# Models - LineageNode
# =============================================================================


@pytest.mark.unit
class TestLineageNode:
    """Tests for LineageNode dataclass."""

    def test_creation_with_all_fields(self, sample_node: LineageNode):
        """Node created with all fields set correctly."""
        assert sample_node.node_id == "node-001"
        assert sample_node.entity_type == "Vessel"
        assert sample_node.entity_id == "VES-001"
        assert sample_node.created_at == datetime(2025, 1, 1, tzinfo=timezone.utc)
        assert sample_node.metadata == {"source": "AIS"}

    def test_creation_with_defaults(self):
        """Node created with default values for optional fields."""
        node = LineageNode(
            node_id="n-1",
            entity_type="Port",
            entity_id="PORT-001",
        )
        assert node.metadata == {}
        assert node.created_at is not None
        assert node.created_at.tzinfo is not None


# =============================================================================
# Models - LineageEdge
# =============================================================================


@pytest.mark.unit
class TestLineageEdge:
    """Tests for LineageEdge dataclass."""

    def test_creation_with_all_fields(self, sample_edge: LineageEdge):
        """Edge created with all fields set correctly."""
        assert sample_edge.edge_id == "edge-001"
        assert sample_edge.source_id == "node-001"
        assert sample_edge.target_id == "node-002"
        assert sample_edge.event_type == LineageEventType.DERIVATION
        assert sample_edge.agent == "ETL-Pipeline-1"
        assert sample_edge.activity == "Derived vessel statistics"
        assert sample_edge.metadata == {"version": "1.0"}

    def test_creation_with_defaults(self):
        """Edge created with default values for optional fields."""
        edge = LineageEdge(
            edge_id="e-1",
            source_id="src",
            target_id="tgt",
            event_type=LineageEventType.CREATION,
        )
        assert edge.agent == ""
        assert edge.activity == ""
        assert edge.metadata == {}
        assert edge.timestamp is not None


# =============================================================================
# Models - LineageGraph
# =============================================================================


@pytest.mark.unit
class TestLineageGraph:
    """Tests for LineageGraph dataclass."""

    def test_add_node(self, sample_node: LineageNode):
        """add_node stores node by node_id."""
        graph = LineageGraph()
        graph.add_node(sample_node)
        assert "node-001" in graph.nodes
        assert graph.nodes["node-001"] is sample_node

    def test_add_node_upserts(self, sample_node: LineageNode):
        """add_node overwrites existing node with same node_id."""
        graph = LineageGraph()
        graph.add_node(sample_node)

        updated = LineageNode(
            node_id="node-001",
            entity_type="Vessel",
            entity_id="VES-002",
        )
        graph.add_node(updated)

        assert graph.nodes["node-001"].entity_id == "VES-002"
        assert len(graph.nodes) == 1

    def test_add_edge(self, sample_edge: LineageEdge):
        """add_edge appends edge to the list."""
        graph = LineageGraph()
        graph.add_edge(sample_edge)
        assert len(graph.edges) == 1
        assert graph.edges[0] is sample_edge

    def test_get_ancestors_simple_chain(self, chain_graph: LineageGraph):
        """get_ancestors returns all upstream nodes in a chain."""
        ancestors_of_c = chain_graph.get_ancestors("C")
        assert set(ancestors_of_c) == {"A", "B"}

    def test_get_ancestors_root_has_none(self, chain_graph: LineageGraph):
        """Root node (A) has no ancestors."""
        ancestors_of_a = chain_graph.get_ancestors("A")
        assert ancestors_of_a == []

    def test_get_descendants_from_root(self, chain_graph: LineageGraph):
        """get_descendants from root returns all downstream nodes."""
        descendants_of_a = chain_graph.get_descendants("A")
        assert set(descendants_of_a) == {"B", "C", "D"}

    def test_get_descendants_leaf_has_none(self, chain_graph: LineageGraph):
        """Leaf nodes (C, D) have no descendants."""
        assert chain_graph.get_descendants("C") == []
        assert chain_graph.get_descendants("D") == []


# =============================================================================
# Models - DataSnapshot
# =============================================================================


@pytest.mark.unit
class TestDataSnapshot:
    """Tests for DataSnapshot dataclass."""

    def test_creation_with_all_fields(self):
        """Snapshot created with all fields set correctly."""
        snap = DataSnapshot(
            snapshot_id="snap-001",
            entity_type="Vessel",
            entity_id="VES-001",
            properties={"name": "Test Ship", "tonnage": 5000},
            captured_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
            captured_by="USER-001",
        )
        assert snap.snapshot_id == "snap-001"
        assert snap.properties["tonnage"] == 5000
        assert snap.captured_by == "USER-001"

    def test_creation_with_defaults(self):
        """Snapshot created with default values."""
        snap = DataSnapshot(
            snapshot_id="snap-002",
            entity_type="Port",
            entity_id="PORT-001",
        )
        assert snap.properties == {}
        assert snap.captured_by == ""
        assert snap.captured_at is not None


# =============================================================================
# Policy - RecordingLevel
# =============================================================================


@pytest.mark.unit
class TestRecordingLevel:
    """Tests for RecordingLevel enum."""

    def test_all_levels_present(self):
        """All 5 recording levels are defined."""
        expected = {"NONE", "MINIMAL", "STANDARD", "DETAILED", "FULL"}
        assert {level.value for level in RecordingLevel} == expected

    def test_recording_level_is_str_enum(self):
        """RecordingLevel values are strings."""
        assert RecordingLevel.STANDARD == "STANDARD"
        assert isinstance(RecordingLevel.FULL, str)


# =============================================================================
# Policy - LineagePolicy
# =============================================================================


@pytest.mark.unit
class TestLineagePolicy:
    """Tests for LineagePolicy."""

    def test_default_level_is_standard(self):
        """Default policy uses STANDARD recording level."""
        policy = LineagePolicy()
        assert policy.default_level == RecordingLevel.STANDARD

    def test_custom_default_level(self):
        """Custom default level is respected."""
        policy = LineagePolicy(default_level=RecordingLevel.FULL)
        assert policy.default_level == RecordingLevel.FULL

    def test_set_and_get_level(self):
        """set_level and get_level work correctly."""
        policy = LineagePolicy()
        policy.set_level("ExperimentalDataset", RecordingLevel.FULL)
        assert policy.get_level("ExperimentalDataset") == RecordingLevel.FULL

    def test_get_level_falls_back_to_default(self):
        """get_level returns default when no rule set for entity type."""
        policy = LineagePolicy(default_level=RecordingLevel.MINIMAL)
        assert policy.get_level("UnknownType") == RecordingLevel.MINIMAL


# =============================================================================
# Policy - should_record
# =============================================================================


@pytest.mark.unit
class TestShouldRecord:
    """Tests for LineagePolicy.should_record()."""

    def test_none_never_records(self):
        """NONE level never records any event."""
        policy = LineagePolicy(default_level=RecordingLevel.NONE)
        for event_type in LineageEventType:
            assert policy.should_record("Vessel", event_type) is False

    def test_minimal_records_creation_and_deletion(self):
        """MINIMAL records CREATION and DELETION only."""
        policy = LineagePolicy(default_level=RecordingLevel.MINIMAL)
        assert policy.should_record("Vessel", LineageEventType.CREATION) is True
        assert policy.should_record("Vessel", LineageEventType.DELETION) is True
        assert policy.should_record("Vessel", LineageEventType.TRANSFORMATION) is False
        assert policy.should_record("Vessel", LineageEventType.EXPORT) is False

    def test_standard_records_creation_transformation_deletion_merge(self):
        """STANDARD records CREATION, TRANSFORMATION, DELETION, MERGE."""
        policy = LineagePolicy(default_level=RecordingLevel.STANDARD)
        assert policy.should_record("Vessel", LineageEventType.CREATION) is True
        assert policy.should_record("Vessel", LineageEventType.TRANSFORMATION) is True
        assert policy.should_record("Vessel", LineageEventType.DELETION) is True
        assert policy.should_record("Vessel", LineageEventType.MERGE) is True
        assert policy.should_record("Vessel", LineageEventType.EXPORT) is False
        assert policy.should_record("Vessel", LineageEventType.DERIVATION) is False

    def test_detailed_records_all_except_export(self):
        """DETAILED records everything except EXPORT."""
        policy = LineagePolicy(default_level=RecordingLevel.DETAILED)
        for event_type in LineageEventType:
            expected = event_type != LineageEventType.EXPORT
            assert policy.should_record("Vessel", event_type) is expected, (
                f"Expected {expected} for {event_type} at DETAILED level"
            )

    def test_full_records_everything(self):
        """FULL level records all event types."""
        policy = LineagePolicy(default_level=RecordingLevel.FULL)
        for event_type in LineageEventType:
            assert policy.should_record("Vessel", event_type) is True

    def test_per_entity_override(self):
        """Entity-specific rules override default level."""
        policy = LineagePolicy(default_level=RecordingLevel.NONE)
        policy.set_level("SecretData", RecordingLevel.FULL)

        assert policy.should_record("Vessel", LineageEventType.CREATION) is False
        assert policy.should_record("SecretData", LineageEventType.CREATION) is True
        assert policy.should_record("SecretData", LineageEventType.EXPORT) is True


# =============================================================================
# Policy - should_snapshot
# =============================================================================


@pytest.mark.unit
class TestShouldSnapshot:
    """Tests for LineagePolicy.should_snapshot()."""

    def test_snapshot_enabled_at_detailed(self):
        """Snapshots enabled at DETAILED level."""
        policy = LineagePolicy(default_level=RecordingLevel.DETAILED)
        assert policy.should_snapshot("Vessel") is True

    def test_snapshot_enabled_at_full(self):
        """Snapshots enabled at FULL level."""
        policy = LineagePolicy(default_level=RecordingLevel.FULL)
        assert policy.should_snapshot("Vessel") is True

    def test_snapshot_disabled_at_standard(self):
        """Snapshots disabled at STANDARD and below."""
        for level in [RecordingLevel.NONE, RecordingLevel.MINIMAL, RecordingLevel.STANDARD]:
            policy = LineagePolicy(default_level=level)
            assert policy.should_snapshot("Vessel") is False, (
                f"Expected snapshot disabled at {level}"
            )


# =============================================================================
# Policy - from_data_classification
# =============================================================================


@pytest.mark.unit
class TestFromDataClassification:
    """Tests for LineagePolicy.from_data_classification()."""

    def test_level_1_public_maps_to_minimal(self):
        """PUBLIC (level 1) maps to MINIMAL recording."""
        assert LineagePolicy.from_data_classification(1) == RecordingLevel.MINIMAL

    def test_level_2_internal_maps_to_standard(self):
        """INTERNAL (level 2) maps to STANDARD recording."""
        assert LineagePolicy.from_data_classification(2) == RecordingLevel.STANDARD

    def test_level_3_confidential_maps_to_standard(self):
        """CONFIDENTIAL (level 3) maps to STANDARD recording."""
        assert LineagePolicy.from_data_classification(3) == RecordingLevel.STANDARD

    def test_level_4_secret_maps_to_detailed(self):
        """SECRET (level 4) maps to DETAILED recording."""
        assert LineagePolicy.from_data_classification(4) == RecordingLevel.DETAILED

    def test_level_5_top_secret_maps_to_full(self):
        """TOP_SECRET (level 5) maps to FULL recording."""
        assert LineagePolicy.from_data_classification(5) == RecordingLevel.FULL

    def test_invalid_level_raises_value_error(self):
        """Invalid classification level raises ValueError."""
        with pytest.raises(ValueError, match="Invalid data classification level"):
            LineagePolicy.from_data_classification(0)
        with pytest.raises(ValueError, match="Invalid data classification level"):
            LineagePolicy.from_data_classification(6)


# =============================================================================
# Recorder - record_event
# =============================================================================


@pytest.mark.unit
class TestRecorderRecordEvent:
    """Tests for LineageRecorder.record_event()."""

    def test_record_event_creates_node_and_edge(self):
        """record_event creates a LineageNode and LineageEdge."""
        recorder = LineageRecorder()
        edge = recorder.record_event(
            entity_type="Vessel",
            entity_id="VES-001",
            event_type=LineageEventType.CREATION,
            agent="ETL-1",
            activity="Created vessel",
        )

        assert edge is not None
        graph = recorder.get_graph()
        assert len(graph.nodes) == 1
        assert len(graph.edges) == 1

        node = list(graph.nodes.values())[0]
        assert node.entity_type == "Vessel"
        assert node.entity_id == "VES-001"

    def test_record_event_reuses_existing_node(self):
        """Multiple events for the same entity reuse the node."""
        recorder = LineageRecorder()
        recorder.record_event(
            entity_type="Vessel",
            entity_id="VES-001",
            event_type=LineageEventType.CREATION,
            agent="ETL-1",
            activity="Created",
        )
        recorder.record_event(
            entity_type="Vessel",
            entity_id="VES-001",
            event_type=LineageEventType.TRANSFORMATION,
            agent="ETL-1",
            activity="Updated",
        )

        graph = recorder.get_graph()
        assert len(graph.nodes) == 1
        assert len(graph.edges) == 2

    def test_record_event_with_metadata(self):
        """record_event passes metadata to the edge."""
        recorder = LineageRecorder()
        edge = recorder.record_event(
            entity_type="Vessel",
            entity_id="VES-001",
            event_type=LineageEventType.CREATION,
            agent="ETL-1",
            activity="Created",
            metadata={"source": "AIS", "version": 2},
        )

        assert edge is not None
        assert edge.metadata == {"source": "AIS", "version": 2}


# =============================================================================
# Recorder - policy respect
# =============================================================================


@pytest.mark.unit
class TestRecorderPolicyRespect:
    """Tests for LineageRecorder respecting policy rules."""

    def test_skips_event_when_policy_says_no(self):
        """record_event returns None when policy.should_record is False."""
        policy = LineagePolicy(default_level=RecordingLevel.NONE)
        recorder = LineageRecorder(policy=policy)

        edge = recorder.record_event(
            entity_type="Vessel",
            entity_id="VES-001",
            event_type=LineageEventType.CREATION,
            agent="ETL-1",
            activity="Should be skipped",
        )

        assert edge is None
        assert len(recorder.get_graph().nodes) == 0

    def test_records_when_policy_allows(self):
        """record_event records when policy allows the event type."""
        policy = LineagePolicy(default_level=RecordingLevel.MINIMAL)
        recorder = LineageRecorder(policy=policy)

        # MINIMAL allows CREATION
        edge = recorder.record_event(
            entity_type="Vessel",
            entity_id="VES-001",
            event_type=LineageEventType.CREATION,
            agent="ETL-1",
            activity="Created",
        )
        assert edge is not None

        # MINIMAL does NOT allow TRANSFORMATION
        edge2 = recorder.record_event(
            entity_type="Vessel",
            entity_id="VES-001",
            event_type=LineageEventType.TRANSFORMATION,
            agent="ETL-1",
            activity="Should be skipped",
        )
        assert edge2 is None

    def test_per_entity_policy_in_recorder(self):
        """Recorder respects per-entity-type policy overrides."""
        policy = LineagePolicy(default_level=RecordingLevel.NONE)
        policy.set_level("ImportantData", RecordingLevel.FULL)
        recorder = LineageRecorder(policy=policy)

        # Default NONE: skip
        edge1 = recorder.record_event(
            entity_type="Vessel",
            entity_id="VES-001",
            event_type=LineageEventType.CREATION,
            agent="ETL-1",
            activity="Skipped",
        )
        assert edge1 is None

        # Override FULL: record
        edge2 = recorder.record_event(
            entity_type="ImportantData",
            entity_id="IMP-001",
            event_type=LineageEventType.EXPORT,
            agent="ETL-1",
            activity="Exported",
        )
        assert edge2 is not None


# =============================================================================
# Recorder - record_derivation
# =============================================================================


@pytest.mark.unit
class TestRecorderRecordDerivation:
    """Tests for LineageRecorder.record_derivation()."""

    def test_record_derivation_creates_two_nodes_and_edge(self):
        """record_derivation creates source node, target node, and edge."""
        policy = LineagePolicy(default_level=RecordingLevel.FULL)
        recorder = LineageRecorder(policy=policy)

        edge = recorder.record_derivation(
            source_type="RawDataset",
            source_id="RAW-001",
            target_type="ProcessedDataset",
            target_id="PROC-001",
            agent="Pipeline-1",
            activity="ETL transformation",
        )

        assert edge is not None
        assert edge.event_type == LineageEventType.DERIVATION
        graph = recorder.get_graph()
        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1

    def test_record_derivation_respects_policy(self):
        """record_derivation returns None when policy disallows DERIVATION."""
        # MINIMAL does not include DERIVATION
        policy = LineagePolicy(default_level=RecordingLevel.MINIMAL)
        recorder = LineageRecorder(policy=policy)

        edge = recorder.record_derivation(
            source_type="RawDataset",
            source_id="RAW-001",
            target_type="ProcessedDataset",
            target_id="PROC-001",
            agent="Pipeline-1",
            activity="Should be skipped",
        )

        assert edge is None


# =============================================================================
# Recorder - take_snapshot
# =============================================================================


@pytest.mark.unit
class TestRecorderTakeSnapshot:
    """Tests for LineageRecorder.take_snapshot()."""

    def test_snapshot_captured_at_detailed_level(self):
        """Snapshot captured when policy level is DETAILED."""
        policy = LineagePolicy(default_level=RecordingLevel.DETAILED)
        recorder = LineageRecorder(policy=policy)

        snap = recorder.take_snapshot(
            entity_type="Vessel",
            entity_id="VES-001",
            properties={"name": "Test Ship", "tonnage": 5000},
            captured_by="USER-001",
        )

        assert snap is not None
        assert snap.entity_type == "Vessel"
        assert snap.entity_id == "VES-001"
        assert snap.properties == {"name": "Test Ship", "tonnage": 5000}
        assert snap.captured_by == "USER-001"

    def test_snapshot_skipped_at_standard_level(self):
        """Snapshot skipped when policy level is STANDARD."""
        policy = LineagePolicy(default_level=RecordingLevel.STANDARD)
        recorder = LineageRecorder(policy=policy)

        snap = recorder.take_snapshot(
            entity_type="Vessel",
            entity_id="VES-001",
            properties={"name": "Test Ship"},
            captured_by="USER-001",
        )

        assert snap is None

    def test_snapshot_makes_defensive_copy(self):
        """Snapshot properties are a defensive copy of the input."""
        policy = LineagePolicy(default_level=RecordingLevel.FULL)
        recorder = LineageRecorder(policy=policy)

        props = {"name": "Original"}
        snap = recorder.take_snapshot(
            entity_type="Vessel",
            entity_id="VES-001",
            properties=props,
            captured_by="USER-001",
        )

        # Mutate original
        props["name"] = "Mutated"

        assert snap is not None
        assert snap.properties["name"] == "Original"


# =============================================================================
# Recorder - get_lineage_for
# =============================================================================


@pytest.mark.unit
class TestRecorderGetLineageFor:
    """Tests for LineageRecorder.get_lineage_for()."""

    def test_get_lineage_for_returns_subgraph(self):
        """get_lineage_for returns subgraph with ancestors and descendants."""
        policy = LineagePolicy(default_level=RecordingLevel.FULL)
        recorder = LineageRecorder(policy=policy)

        # A -> B -> C (derivation chain)
        recorder.record_derivation("Raw", "A", "Processed", "B", "ETL", "step1")
        recorder.record_derivation("Processed", "B", "Final", "C", "ETL", "step2")

        subgraph = recorder.get_lineage_for("B")

        # B's lineage should include A (ancestor), B itself, and C (descendant)
        entity_ids = {n.entity_id for n in subgraph.nodes.values()}
        assert "A" in entity_ids
        assert "B" in entity_ids
        assert "C" in entity_ids

    def test_get_lineage_for_unknown_entity(self):
        """get_lineage_for returns empty graph for unknown entity."""
        recorder = LineageRecorder()
        subgraph = recorder.get_lineage_for("NONEXISTENT")

        assert len(subgraph.nodes) == 0
        assert len(subgraph.edges) == 0


# =============================================================================
# Recorder - clear
# =============================================================================


@pytest.mark.unit
class TestRecorderClear:
    """Tests for LineageRecorder.clear()."""

    def test_clear_resets_all_state(self):
        """clear() resets nodes, edges, and entity map."""
        recorder = LineageRecorder()
        recorder.record_event(
            entity_type="Vessel",
            entity_id="VES-001",
            event_type=LineageEventType.CREATION,
            agent="ETL-1",
            activity="Created",
        )

        assert len(recorder.get_graph().nodes) == 1
        recorder.clear()

        assert len(recorder.get_graph().nodes) == 0
        assert len(recorder.get_graph().edges) == 0


# =============================================================================
# Queries - Cypher content validation
# =============================================================================


@pytest.mark.unit
class TestQueriesCypherContent:
    """Tests for Cypher query strings in queries module."""

    def test_merge_lineage_node_contains_merge(self):
        """MERGE_LINEAGE_NODE contains MERGE and LineageNode label."""
        assert "MERGE" in queries.MERGE_LINEAGE_NODE
        assert "LineageNode" in queries.MERGE_LINEAGE_NODE

    def test_merge_lineage_edge_contains_create_and_derived_from(self):
        """MERGE_LINEAGE_EDGE contains CREATE and DERIVED_FROM."""
        assert "CREATE" in queries.MERGE_LINEAGE_EDGE
        assert "DERIVED_FROM" in queries.MERGE_LINEAGE_EDGE

    def test_merge_snapshot_contains_data_snapshot(self):
        """MERGE_SNAPSHOT contains DataSnapshot and HAS_SNAPSHOT."""
        assert "DataSnapshot" in queries.MERGE_SNAPSHOT
        assert "HAS_SNAPSHOT" in queries.MERGE_SNAPSHOT

    def test_get_ancestors_uses_variable_length_path(self):
        """GET_ANCESTORS uses variable-length path pattern."""
        assert "DERIVED_FROM*" in queries.GET_ANCESTORS
        assert "ancestor" in queries.GET_ANCESTORS.lower()

    def test_get_descendants_uses_variable_length_path(self):
        """GET_DESCENDANTS uses variable-length path pattern."""
        assert "DERIVED_FROM*" in queries.GET_DESCENDANTS
        assert "descendant" in queries.GET_DESCENDANTS.lower()


# =============================================================================
# Queries - Parameter placeholders
# =============================================================================


@pytest.mark.unit
class TestQueriesParameters:
    """Tests for parameter placeholders in Cypher queries."""

    def test_merge_lineage_node_has_parameters(self):
        """MERGE_LINEAGE_NODE uses $nodeId, $entityType, $entityId."""
        query = queries.MERGE_LINEAGE_NODE
        assert "$nodeId" in query
        assert "$entityType" in query
        assert "$entityId" in query

    def test_merge_lineage_edge_has_parameters(self):
        """MERGE_LINEAGE_EDGE uses $sourceId, $targetId, $eventType, etc."""
        query = queries.MERGE_LINEAGE_EDGE
        assert "$sourceId" in query
        assert "$targetId" in query
        assert "$eventType" in query
        assert "$agent" in query

    def test_get_queries_have_entity_parameters(self):
        """GET queries use $entityId and $entityType parameters."""
        for query_name in ["GET_ANCESTORS", "GET_DESCENDANTS",
                           "GET_FULL_LINEAGE", "GET_LINEAGE_TIMELINE"]:
            query = getattr(queries, query_name)
            assert "$entityId" in query, f"{query_name} missing $entityId"
            assert "$entityType" in query, f"{query_name} missing $entityType"


# =============================================================================
# Integration-style unit tests (cross-module)
# =============================================================================


@pytest.mark.unit
class TestCrossModuleIntegration:
    """Cross-module integration tests (still pure Python, no Neo4j)."""

    def test_full_lineage_pipeline(self):
        """End-to-end: policy + recorder + graph traversal."""
        policy = LineagePolicy(default_level=RecordingLevel.FULL)
        recorder = LineageRecorder(policy=policy)

        # Simulate a 3-step ETL pipeline
        recorder.record_event(
            entity_type="RawData", entity_id="RAW-001",
            event_type=LineageEventType.INGESTION,
            agent="Crawler", activity="Ingested from external source",
        )
        recorder.record_derivation(
            source_type="RawData", source_id="RAW-001",
            target_type="CleanData", target_id="CLN-001",
            agent="ETL-Pipeline", activity="Data cleaning",
        )
        recorder.record_derivation(
            source_type="CleanData", source_id="CLN-001",
            target_type="Report", target_id="RPT-001",
            agent="Reporter", activity="Generated report",
        )

        graph = recorder.get_graph()
        assert len(graph.nodes) == 3
        # 1 ingestion self-edge + 2 derivation edges
        assert len(graph.edges) == 3

        # Find the node_id for CLN-001
        cln_node_id = None
        for node in graph.nodes.values():
            if node.entity_id == "CLN-001":
                cln_node_id = node.node_id
                break
        assert cln_node_id is not None

        ancestors = graph.get_ancestors(cln_node_id)
        # RAW-001 is ancestor of CLN-001
        ancestor_entities = {
            graph.nodes[nid].entity_id for nid in ancestors
        }
        assert "RAW-001" in ancestor_entities

    def test_policy_from_classification_to_recorder(self):
        """DataClassification level -> RecordingLevel -> Recorder behavior."""
        # SECRET (level 4) -> DETAILED
        level = LineagePolicy.from_data_classification(4)
        assert level == RecordingLevel.DETAILED

        policy = LineagePolicy(default_level=level)
        recorder = LineageRecorder(policy=policy)

        # DETAILED records INGESTION but not EXPORT
        edge1 = recorder.record_event(
            entity_type="SecretData", entity_id="SEC-001",
            event_type=LineageEventType.INGESTION,
            agent="Importer", activity="Imported classified data",
        )
        assert edge1 is not None

        edge2 = recorder.record_event(
            entity_type="SecretData", entity_id="SEC-001",
            event_type=LineageEventType.EXPORT,
            agent="Exporter", activity="Should be blocked",
        )
        assert edge2 is None

        # DETAILED enables snapshots
        snap = recorder.take_snapshot(
            entity_type="SecretData", entity_id="SEC-001",
            properties={"classification": "SECRET"},
            captured_by="Auditor",
        )
        assert snap is not None

    def test_get_full_lineage_query_is_valid_cypher_structure(self):
        """GET_FULL_LINEAGE has valid Cypher structure markers."""
        query = queries.GET_FULL_LINEAGE
        assert "MATCH" in query
        assert "RETURN" in query
        assert "OPTIONAL MATCH" in query
        assert "WITH" in query
