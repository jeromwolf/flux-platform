"""Lineage recorder for building in-memory lineage graphs.

The recorder acts as a high-level API for tracking data provenance.
It checks the :class:`~kg.lineage.policy.LineagePolicy` before recording
events and manages the lifecycle of :class:`~kg.lineage.models.LineageNode`,
:class:`~kg.lineage.models.LineageEdge`, and
:class:`~kg.lineage.models.DataSnapshot` objects.

The recorder does NOT connect to Neo4j directly. Use the Cypher queries
in :mod:`kg.lineage.queries` to persist the in-memory graph to the database.

Usage::

    from kg.lineage.recorder import LineageRecorder
    from kg.lineage.models import LineageEventType

    recorder = LineageRecorder()
    edge = recorder.record_event(
        entity_type="Vessel",
        entity_id="VES-001",
        event_type=LineageEventType.CREATION,
        agent="ETL-Pipeline-1",
        activity="Imported vessel data from AIS feed",
    )
    graph = recorder.get_graph()
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from kg.lineage.models import (
    DataSnapshot,
    LineageEdge,
    LineageEventType,
    LineageGraph,
    LineageNode,
)
from kg.lineage.policy import LineagePolicy, RecordingLevel
from kg.lineage.queries import MERGE_LINEAGE_EDGE, MERGE_LINEAGE_NODE

logger = logging.getLogger(__name__)


def _new_id() -> str:
    """Generate a new UUID4 string identifier."""
    return str(uuid4())


def _now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


class LineageRecorder:
    """High-level lineage recording API.

    Manages an in-memory :class:`LineageGraph` and respects the configured
    :class:`LineagePolicy` when deciding whether to record events or
    capture snapshots.

    Args:
        policy: Lineage recording policy. If None, a default STANDARD
            policy is used.
    """

    def __init__(self, policy: LineagePolicy | None = None) -> None:
        self._policy = policy or LineagePolicy(
            default_level=RecordingLevel.STANDARD
        )
        self._graph = LineageGraph()
        self._snapshots: list[DataSnapshot] = []
        # Track entity_id -> node_id mapping for fast lookup
        self._entity_node_map: dict[str, str] = {}

    def _get_or_create_node(
        self,
        entity_type: str,
        entity_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> LineageNode:
        """Get existing node for an entity or create a new one.

        Args:
            entity_type: Neo4j label.
            entity_id: The actual ID property value.
            metadata: Optional metadata for new nodes.

        Returns:
            The existing or newly created LineageNode.
        """
        # Use a composite key to handle same entity_id across different types
        lookup_key = f"{entity_type}:{entity_id}"
        existing_id = self._entity_node_map.get(lookup_key)
        if existing_id and existing_id in self._graph.nodes:
            return self._graph.nodes[existing_id]

        node = LineageNode(
            node_id=_new_id(),
            entity_type=entity_type,
            entity_id=entity_id,
            created_at=_now(),
            metadata=metadata or {},
        )
        self._graph.add_node(node)
        self._entity_node_map[lookup_key] = node.node_id
        return node

    def record_event(
        self,
        entity_type: str,
        entity_id: str,
        event_type: LineageEventType,
        agent: str,
        activity: str,
        metadata: dict[str, Any] | None = None,
    ) -> LineageEdge | None:
        """Record a lineage event for an entity.

        Checks the policy before recording. Creates or reuses the
        :class:`LineageNode` for the entity and creates a self-referencing
        :class:`LineageEdge` representing the event.

        Args:
            entity_type: Neo4j label (e.g., "Vessel").
            entity_id: The actual ID property value (e.g., "VES-001").
            event_type: The type of lineage event.
            agent: Who performed the action.
            activity: Description of what happened.
            metadata: Optional additional metadata.

        Returns:
            The created LineageEdge, or None if the policy says to skip.
        """
        if not self._policy.should_record(entity_type, event_type):
            return None

        node = self._get_or_create_node(entity_type, entity_id, metadata)

        edge = LineageEdge(
            edge_id=_new_id(),
            source_id=node.node_id,
            target_id=node.node_id,
            event_type=event_type,
            timestamp=_now(),
            agent=agent,
            activity=activity,
            metadata=metadata or {},
        )
        self._graph.add_edge(edge)
        return edge

    def record_derivation(
        self,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        agent: str,
        activity: str,
    ) -> LineageEdge | None:
        """Record a derivation event (source -> target).

        Convenience method for DERIVATION events where one entity is
        derived from another.

        Args:
            source_type: Neo4j label of the source entity.
            source_id: ID of the source entity.
            target_type: Neo4j label of the target entity.
            target_id: ID of the target entity.
            agent: Who performed the derivation.
            activity: Description of the derivation.

        Returns:
            The created LineageEdge, or None if the policy says to skip.
        """
        if not self._policy.should_record(
            target_type, LineageEventType.DERIVATION
        ):
            return None

        source_node = self._get_or_create_node(source_type, source_id)
        target_node = self._get_or_create_node(target_type, target_id)

        edge = LineageEdge(
            edge_id=_new_id(),
            source_id=source_node.node_id,
            target_id=target_node.node_id,
            event_type=LineageEventType.DERIVATION,
            timestamp=_now(),
            agent=agent,
            activity=activity,
        )
        self._graph.add_edge(edge)
        return edge

    def take_snapshot(
        self,
        entity_type: str,
        entity_id: str,
        properties: dict[str, Any],
        captured_by: str,
    ) -> DataSnapshot | None:
        """Capture a point-in-time snapshot of an entity.

        Only captures if the policy allows snapshots for the entity type
        (DETAILED or FULL recording level).

        Args:
            entity_type: Neo4j label.
            entity_id: The actual ID property value.
            properties: Current properties of the entity (will be copied).
            captured_by: Who triggered the snapshot.

        Returns:
            The created DataSnapshot, or None if the policy says to skip.
        """
        if not self._policy.should_snapshot(entity_type):
            return None

        snapshot = DataSnapshot(
            snapshot_id=_new_id(),
            entity_type=entity_type,
            entity_id=entity_id,
            properties=dict(properties),  # defensive copy
            captured_at=_now(),
            captured_by=captured_by,
        )
        self._snapshots.append(snapshot)
        return snapshot

    def get_graph(self) -> LineageGraph:
        """Return the full in-memory lineage graph.

        Returns:
            The current LineageGraph with all recorded nodes and edges.
        """
        return self._graph

    def get_lineage_for(self, entity_id: str) -> LineageGraph:
        """Return a subgraph containing only the lineage of a specific entity.

        Includes the entity itself plus all ancestors and descendants.

        Args:
            entity_id: The entity_id (not node_id) to build lineage for.

        Returns:
            A new LineageGraph containing only the relevant nodes and edges.
        """
        # Find the node_id for this entity_id
        target_node_id: str | None = None
        for node in self._graph.nodes.values():
            if node.entity_id == entity_id:
                target_node_id = node.node_id
                break

        if target_node_id is None:
            return LineageGraph()

        # Collect all related node_ids
        ancestors = set(self._graph.get_ancestors(target_node_id))
        descendants = set(self._graph.get_descendants(target_node_id))
        related_ids = ancestors | descendants | {target_node_id}

        # Build subgraph
        subgraph = LineageGraph()
        for nid in related_ids:
            node = self._graph.nodes.get(nid)
            if node is not None:
                subgraph.add_node(node)

        for edge in self._graph.edges:
            if edge.source_id in related_ids and edge.target_id in related_ids:
                subgraph.add_edge(edge)

        return subgraph

    def flush(self, session: Any) -> int:
        """인메모리 리니지 그래프를 Neo4j에 영속화.

        Args:
            session: Neo4j session (sync)

        Returns:
            영속화된 노드 + 엣지 수
        """
        graph = self.get_graph()
        if not graph.nodes and not graph.edges:
            return 0

        count = 0
        try:
            # 노드 먼저 영속화
            for node in graph.nodes.values():
                session.run(
                    MERGE_LINEAGE_NODE,
                    {
                        "nodeId": node.node_id,
                        "entityType": node.entity_type,
                        "entityId": node.entity_id,
                        "createdAt": node.created_at.isoformat() if node.created_at else None,
                        "metadata": str(node.metadata) if node.metadata else "",
                    },
                )
                count += 1

            # 엣지 영속화
            for edge in graph.edges:
                session.run(
                    MERGE_LINEAGE_EDGE,
                    {
                        "sourceId": edge.source_id,
                        "targetId": edge.target_id,
                        "edgeId": edge.edge_id,
                        "eventType": edge.event_type.value if hasattr(edge.event_type, "value") else str(edge.event_type),
                        "timestamp": edge.timestamp.isoformat() if edge.timestamp else None,
                        "agent": edge.agent or "system",
                        "activity": edge.activity or "",
                        "metadata": str(edge.metadata) if edge.metadata else "",
                    },
                )
                count += 1

            logger.info(
                "Lineage flushed: %d nodes, %d edges",
                len(graph.nodes),
                len(graph.edges),
            )
        except Exception as e:
            logger.error("Lineage flush failed: %s", e)

        return count

    def clear(self) -> None:
        """Reset the recorder, clearing all recorded data."""
        self._graph = LineageGraph()
        self._snapshots = []
        self._entity_node_map = {}
