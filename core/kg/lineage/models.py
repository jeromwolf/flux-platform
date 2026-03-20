"""Data lineage domain models (W3C PROV-O inspired).

Provides the core data structures for tracking data provenance and lineage
within the Maritime Knowledge Graph platform. Models follow the W3C PROV-O
ontology patterns with three core concepts:

- **Entity** (what): A data object whose lineage is tracked.
- **Activity** (how): A process that creates, transforms, or derives data.
- **Agent** (who): A person, system, or pipeline that triggers an activity.

All models use ``from __future__ import annotations`` for forward references
and follow the project conventions of frozen dataclasses where immutability
is desired, and ``str`` Enums for Neo4j-compatible serialization.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

# =========================================================================
# Enums
# =========================================================================


class LineageEventType(str, Enum):
    """Types of lineage events that can be recorded.

    Maps to W3C PROV-O activity types with maritime-domain extensions.
    """

    CREATION = "CREATION"
    TRANSFORMATION = "TRANSFORMATION"
    DERIVATION = "DERIVATION"
    INGESTION = "INGESTION"
    EXPORT = "EXPORT"
    DELETION = "DELETION"
    MERGE = "MERGE"
    SPLIT = "SPLIT"


class ProvenanceRole(str, Enum):
    """W3C PROV-O provenance roles.

    Attributes:
        AGENT: Who performed the action (person, system, pipeline).
        ENTITY: What was acted upon (data object, dataset).
        ACTIVITY: How the action was performed (process, transformation).
    """

    AGENT = "AGENT"
    ENTITY = "ENTITY"
    ACTIVITY = "ACTIVITY"


# =========================================================================
# Data Models
# =========================================================================


@dataclass
class LineageNode:
    """A node in the lineage graph representing a tracked entity.

    Attributes:
        node_id: Unique identifier for this lineage node (UUID).
        entity_type: Neo4j label of the tracked entity (e.g., "Vessel").
        entity_id: The actual ID property value (e.g., "VES-001").
        created_at: Timestamp when this lineage node was first recorded.
        metadata: Additional key-value metadata for the node.
    """

    node_id: str
    entity_type: str
    entity_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LineageEdge:
    """A directed edge in the lineage graph representing a provenance event.

    Edges flow from source to target, indicating that the target was
    derived from, transformed from, or otherwise related to the source.

    Attributes:
        edge_id: Unique identifier for this edge (UUID).
        source_id: LineageNode.node_id of the source entity.
        target_id: LineageNode.node_id of the target entity.
        event_type: The type of lineage event.
        timestamp: When the event occurred.
        agent: Who performed the action (e.g., "ETL-Pipeline-1", "USER-001").
        activity: Description of what happened.
        metadata: Additional key-value metadata for the edge.
    """

    edge_id: str
    source_id: str
    target_id: str
    event_type: LineageEventType
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    agent: str = ""
    activity: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LineageGraph:
    """In-memory lineage graph supporting traversal queries.

    Maintains a collection of :class:`LineageNode` and :class:`LineageEdge`
    objects and provides BFS-based ancestor/descendant lookups.

    Attributes:
        nodes: Mapping of node_id to LineageNode.
        edges: List of all LineageEdge instances.
    """

    nodes: dict[str, LineageNode] = field(default_factory=dict)
    edges: list[LineageEdge] = field(default_factory=list)

    def add_node(self, node: LineageNode) -> None:
        """Add a node to the graph (upserts by node_id).

        Args:
            node: The lineage node to add.
        """
        self.nodes[node.node_id] = node

    def add_edge(self, edge: LineageEdge) -> None:
        """Add an edge to the graph.

        Args:
            edge: The lineage edge to add.
        """
        self.edges.append(edge)

    def get_ancestors(self, node_id: str) -> list[str]:
        """Find all ancestor node_ids via BFS traversal.

        Follows edges backward (target -> source) to discover all nodes
        that contributed to the given node.

        Args:
            node_id: The starting node identifier.

        Returns:
            List of ancestor node_ids (excluding the starting node).
        """
        # Build reverse adjacency: target -> [source1, source2, ...]
        reverse_adj: dict[str, list[str]] = {}
        for edge in self.edges:
            reverse_adj.setdefault(edge.target_id, []).append(edge.source_id)

        visited: set[str] = set()
        queue: deque[str] = deque()

        for source_id in reverse_adj.get(node_id, []):
            if source_id not in visited:
                visited.add(source_id)
                queue.append(source_id)

        while queue:
            current = queue.popleft()
            for source_id in reverse_adj.get(current, []):
                if source_id not in visited:
                    visited.add(source_id)
                    queue.append(source_id)

        return list(visited)

    def get_descendants(self, node_id: str) -> list[str]:
        """Find all descendant node_ids via BFS traversal.

        Follows edges forward (source -> target) to discover all nodes
        derived from the given node.

        Args:
            node_id: The starting node identifier.

        Returns:
            List of descendant node_ids (excluding the starting node).
        """
        # Build forward adjacency: source -> [target1, target2, ...]
        forward_adj: dict[str, list[str]] = {}
        for edge in self.edges:
            forward_adj.setdefault(edge.source_id, []).append(edge.target_id)

        visited: set[str] = set()
        queue: deque[str] = deque()

        for target_id in forward_adj.get(node_id, []):
            if target_id not in visited:
                visited.add(target_id)
                queue.append(target_id)

        while queue:
            current = queue.popleft()
            for target_id in forward_adj.get(current, []):
                if target_id not in visited:
                    visited.add(target_id)
                    queue.append(target_id)

        return list(visited)


@dataclass
class DataSnapshot:
    """A frozen point-in-time copy of an entity's properties.

    Used for audit trails and change tracking when the lineage policy
    requires detailed or full recording.

    Attributes:
        snapshot_id: Unique identifier for this snapshot (UUID).
        entity_type: Neo4j label of the entity.
        entity_id: The actual ID property value.
        properties: Frozen copy of entity properties at capture time.
        captured_at: When the snapshot was taken.
        captured_by: Who or what triggered the snapshot.
    """

    snapshot_id: str
    entity_type: str
    entity_id: str
    properties: dict[str, Any] = field(default_factory=dict)
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    captured_by: str = ""


def _new_id() -> str:
    """Generate a new UUID4 string identifier."""
    return str(uuid4())
